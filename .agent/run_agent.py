import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import TypeVar

from openai import (
    APIConnectionError,
    APITimeoutError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, Field, ValidationError

REPO_ROOT = Path(".").resolve()
PROMPT_PATH = REPO_ROOT / ".agent" / "prompts" / "dev_v1.md"
REPORT_PATH = Path(os.getenv("RUNNER_TEMP", str(REPO_ROOT))) / "agent_report.md"

MAX_STEPS = int(os.getenv("MAX_STEPS", "3"))
MAX_RUN_TOKENS = int(os.getenv("MAX_RUN_TOKENS", "30000"))
MAX_TOKENS_PER_CALL = 8192

ALLOWED_ROOT_FILES = {"index.html", "style.css"}
ALLOWED_DIRS = {"src", "tests"}

T = TypeVar("T", bound=BaseModel)


class FileEdit(BaseModel):
    path: str = Field(description="Relative path from repo root, e.g. 'src/calculator.js'")
    content: str = Field(description="Full updated file content")


class AgentCodePlan(BaseModel):
    pr_title: str = Field(min_length=5, description="Concise Conventional Commit PR title in English")
    summary: str = Field(min_length=15, description="Short objective summary of changes made")
    files: list[FileEdit] = Field(min_length=1, description="Modified or created files")


class SecurityViolationError(ValueError):
    """Blocks writes outside the repository allowlist."""

class LLMUnavailableError(RuntimeError):
    """Falha transitória de rede/provedor (ex: 503, timeout, rate limit)."""

def load_prompt(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.DOTALL)
    if not match:
        return "v0.0.0", raw.strip()
    fm, body = match.group(1), match.group(2).strip()
    ver = re.search(r"^version:\s*(.+)$", fm, re.MULTILINE)
    return (ver.group(1).strip() if ver else "v0.0.0"), body


def resolve_allowed_path(relative_path: str) -> Path:
    raw = Path(relative_path.replace("\\", "/"))
    if raw.is_absolute():
        raise SecurityViolationError(f"Absolute path blocked: {relative_path}")

    target = (REPO_ROOT / raw).resolve()
    if not target.is_relative_to(REPO_ROOT):
        raise SecurityViolationError(f"Path traversal blocked: {relative_path}")

    rel = target.relative_to(REPO_ROOT)
    parts = rel.parts

    if len(parts) == 1 and parts[0] in ALLOWED_ROOT_FILES:
        return target
    if len(parts) >= 2 and parts[0] in ALLOWED_DIRS and target.suffix == ".js":
        return target

    raise SecurityViolationError(
        f"Path outside allowlist (allowed: index.html, style.css, src/*.js, tests/*.js): {rel}"
    )


def snapshot_repo() -> str:
    """Reads only allowed files to keep context minimal."""
    files: list[Path] = []
    for name in sorted(ALLOWED_ROOT_FILES):
        p = REPO_ROOT / name
        if p.is_file():
            files.append(p)
    for folder in sorted(ALLOWED_DIRS):
        d = REPO_ROOT / folder
        if d.is_dir():
            files.extend(sorted(d.rglob("*.js")))

    blocks = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        content = path.read_text(encoding="utf-8")
        blocks.append(f"### {rel}\n```\n{content}\n```")
    return "\n\n".join(blocks)


def run_validation() -> tuple[bool, str, str]:
    """Deterministic gate: syntax check (node --check) + unit tests (node --test)."""
    for folder in sorted(ALLOWED_DIRS):
        d = REPO_ROOT / folder
        if not d.is_dir():
            continue
        for js_file in sorted(d.rglob("*.js")):
            proc = subprocess.run(
                ["node", "--check", str(js_file)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if proc.returncode != 0:
                out = f"{proc.stdout}\n{proc.stderr}".strip()[-3000:]
                return False, f"node --check ({js_file.name})", out

    proc = subprocess.run(
        ["node", "--test"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    out = f"{proc.stdout}\n{proc.stderr}".strip()[-3000:]
    if proc.returncode != 0:
        return False, "node --test", out
    return True, "all", out


def _extract_json(raw_text: str) -> str:
    cleaned = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


class ResilientLLM:
    def __init__(self) -> None:
        self.primary = os.environ["LLM_MODEL"].strip()
        raw_fb = os.getenv("LLM_FALLBACK_MODELS", "")
        self.fallbacks = [m.strip() for m in raw_fb.split(",") if m.strip()]
        self.tokens_used = 0
        self.last_model = self.primary
        self.client = OpenAI(
            base_url=os.environ["LLM_BASE_URL"].strip(),
            api_key=os.environ["LLM_API_KEY"].strip(),
            timeout=45.0,
            max_retries=0,
        )

    def _call_json_fallback(
        self, model: str, messages: list[dict[str, str]], schema: type[T]
    ) -> tuple[T, int]:
        schema_str = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        patched = list(messages) + [
            {
                "role": "user",
                "content": (
                    "Respond EXCLUSIVELY with valid JSON matching this JSON Schema:\n"
                    f"{schema_str}"
                ),
            }
        ]
        comp = self.client.chat.completions.create(
            model=model,
            messages=patched,
            temperature=0.1,
            max_tokens=MAX_TOKENS_PER_CALL,
        )
        total = comp.usage.total_tokens if comp.usage else 0
        raw = comp.choices[0].message.content or ""
        return schema.model_validate_json(_extract_json(raw)), total

    def call_structured(
        self, messages: list[dict[str, str]], schema: type[T], step: int
    ) -> T:
        if self.tokens_used >= MAX_RUN_TOKENS:
            raise RuntimeError(f"Token budget exceeded: {self.tokens_used}/{MAX_RUN_TOKENS}.")

        models = [self.primary] + [m for m in self.fallbacks if m != self.primary]
        waits = [5, 15]
        last_err: Exception | None = None

        for model in models:
            for attempt in range(len(waits) + 1):
                try:
                    try:
                        comp = self.client.beta.chat.completions.parse(
                            model=model,
                            messages=messages,
                            response_format=schema,
                            temperature=0.1,
                            max_tokens=MAX_TOKENS_PER_CALL,
                        )
                        parsed = comp.choices[0].message.parsed
                        total = comp.usage.total_tokens if comp.usage else 0
                        if parsed is None:
                            raise ValueError("Empty structured parse result.")
                    except (BadRequestError, ValueError):
                        parsed, total = self._call_json_fallback(model, messages, schema)

                    self.tokens_used += total
                    self.last_model = model
                    print(f"[LLM OK] step={step} model={model} tokens={total} total={self.tokens_used}")
                    return parsed

                except (
                    InternalServerError,
                    RateLimitError,
                    APIConnectionError,
                    APITimeoutError,
                    NotFoundError,
                    ValidationError,
                    json.JSONDecodeError,
                ) as exc:
                    last_err = exc
                    if isinstance(exc, NotFoundError):
                        print(f"[WARN] {model} returned 404. Skipping to next model...")
                        break
                    if attempt < len(waits):
                        wait_s = waits[attempt]
                        print(f"[WARN] {model} failed ({type(exc).__name__}). Retrying in {wait_s}s...")
                        time.sleep(wait_s)
                    else:
                        print(f"[WARN] {model} exhausted retries. Falling back...")

        raise LLMUnavailableError(f"All models failed at step {step}: {last_err}") from last_err


def write_report(
    status: str,
    pr_title: str,
    summary: str,
    steps: int,
    tokens: int,
    model: str,
    prompt_ver: str,
    files: list[str],
    test_output: str,
) -> None:
    issue_num = os.getenv("ISSUE_NUMBER", "?")
    report = (
        f"## Dev Agent Report (`{status}`)\n\n"
        f"- **Issue:** #{issue_num}\n"
        f"- **Model:** `{model}` | **Prompt:** `{prompt_ver}`\n"
        f"- **Steps:** {steps}/{MAX_STEPS} | **Total tokens:** {tokens}\n"
        f"- **Modified files:** {', '.join(f'`{f}`' for f in files) or 'none'}\n\n"
        f"### Summary\n{summary}\n\n"
        f"### Validation Output (`node --test`)\n```text\n{test_output}\n```\n\n"
        f"Closes #{issue_num}\n"
    )
    REPORT_PATH.write_text(report, encoding="utf-8")

    gh_env = os.getenv("GITHUB_ENV")
    if gh_env:
        clean_title = pr_title.replace("\n", " ").strip()
        with open(gh_env, "a", encoding="utf-8") as f:
            f.write(f"AGENT_PR_TITLE={clean_title}\n")


def main() -> int:
    issue_num = os.getenv("ISSUE_NUMBER", "0")
    issue_title = os.getenv("ISSUE_TITLE", "").strip()
    issue_body = os.getenv("ISSUE_BODY", "").strip()

    prompt_ver, system_prompt = load_prompt(PROMPT_PATH)
    llm = ResilientLLM()

    last_feedback: str | None = None
    last_files: list[str] = []
    last_plan: AgentCodePlan | None = None
    last_test_output = ""

    print(f"Starting Dev Agent for Issue #{issue_num} (prompt={prompt_ver}, max_steps={MAX_STEPS})")

    for step in range(1, MAX_STEPS + 1):
        repo_state = snapshot_repo()
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"## Issue #{issue_num}: {issue_title}\n\n"
                    f"{issue_body}\n\n"
                    f"## Current repository files\n\n{repo_state}"
                ),
            },
        ]
        if last_feedback:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Previous validation failed.\n{last_feedback}\n\n"
                        "Fix the root cause and return the full corrected files."
                    ),
                }
            )

        try:
            plan = llm.call_structured(messages, AgentCodePlan, step)
            last_plan = plan
        except LLMUnavailableError as exc:
            write_report(
                status="api_unavailable",
                pr_title=f"feat: resolve issue #{issue_num}",
                summary=f"Temporary LLM API unavailability: {exc}",
                steps=step,
                tokens=llm.tokens_used,
                model=llm.last_model,
                prompt_ver=prompt_ver,
                files=last_files,
                test_output=str(exc),
            )
            print(f"[API_UNAVAILABLE] {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            write_report(
                status="error",
                pr_title=f"feat: resolve issue #{issue_num}",
                summary=f"LLM call failed: {exc}",
                steps=step,
                tokens=llm.tokens_used,
                model=llm.last_model,
                prompt_ver=prompt_ver,
                files=last_files,
                test_output=str(exc),
            )
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1

        try:
            written: list[str] = []
            for item in plan.files:
                target = resolve_allowed_path(item.path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item.content, encoding="utf-8")
                written.append(target.relative_to(REPO_ROOT).as_posix())
            last_files = written
            print(f"[WRITE] Updated files: {', '.join(written)}")
        except SecurityViolationError as sec_err:
            print(f"[GUARDRAIL] {sec_err}")
            last_feedback = f"Security guardrail error: {sec_err}"
            continue

        passed, stage, output = run_validation()
        last_test_output = output
        if passed:
            print(f"[SUCCESS] Validation passed at step {step}!")
            write_report(
                status="success",
                pr_title=plan.pr_title,
                summary=plan.summary,
                steps=step,
                tokens=llm.tokens_used,
                model=llm.last_model,
                prompt_ver=prompt_ver,
                files=last_files,
                test_output=output,
            )
            return 0

        print(f"[FAIL] stage={stage} at step {step}. Preparing self-correction...")
        last_feedback = f"Failed stage: {stage}\nOutput:\n{output}"

    write_report(
        status="failed_max_steps",
        pr_title=last_plan.pr_title if last_plan else f"feat: resolve issue #{issue_num}",
        summary=f"Agent reached max steps ({MAX_STEPS}) without passing validation.",
        steps=MAX_STEPS,
        tokens=llm.tokens_used,
        model=llm.last_model,
        prompt_ver=prompt_ver,
        files=last_files,
        test_output=last_test_output,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())