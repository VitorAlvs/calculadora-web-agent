import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pydantic import BaseModel, Field
from run_agent import ResilientLLM, load_prompt

REPO_ROOT = Path(".").resolve()
PROMPT_PATH = REPO_ROOT / ".agent" / "prompts" / "docs_v1.md"
README_PATH = REPO_ROOT / "README.md"


class DocsUpdatePlan(BaseModel):
    needs_update: bool = Field(description="True if README.md needs updating for this Issue/diff")
    change_summary: str = Field(min_length=10, description="Short summary of documentation changes or why none were needed")
    updated_readme: str | None = Field(
        default=None,
        description="Complete updated README.md content when needs_update is True",
    )


def get_git_diff() -> str:
    proc = subprocess.run(
        ["git", "diff", "main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return proc.stdout.strip()[:12000]


def validate_readme_safely(original: str, updated: str) -> tuple[bool, str]:
    """Deterministic anti-truncation and structural integrity guardrails."""
    clean = updated.strip()
    if not clean:
        return False, "Updated README is empty."
    if len(clean) < int(len(original) * 0.85):
        return False, (
            f"Anti-truncation guardrail triggered: updated README ({len(clean)} chars) "
            f"shrank below 85% of original ({len(original)} chars)."
        )
    if not clean.startswith("# "):
        return False, "Missing top-level H1 heading."
    if "Evolução Incremental" not in clean:
        return False, "Missing Roadmap section ('Evolução Incremental')."
    return True, "ok"


def main() -> int:
    if not README_PATH.is_file():
        print("[DOCS] README.md not found. Skipping.")
        return 0

    issue_num = os.getenv("ISSUE_NUMBER", "0")
    issue_title = os.getenv("ISSUE_TITLE", "").strip()
    issue_body = os.getenv("ISSUE_BODY", "").strip()

    diff = get_git_diff()
    if not diff:
        print("[DOCS] Empty diff. Skipping.")
        return 0

    original_readme = README_PATH.read_text(encoding="utf-8")
    prompt_ver, system_prompt = load_prompt(PROMPT_PATH)
    llm = ResilientLLM()

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"## Issue #{issue_num}: {issue_title}\n\n"
                f"{issue_body}\n\n"
                f"## Code Diff (`main...HEAD`)\n```diff\n{diff}\n```\n\n"
                f"## Current README.md\n```markdown\n{original_readme}\n```"
            ),
        },
    ]

    try:
        plan = llm.call_structured(messages, DocsUpdatePlan, step=1)
    except Exception as exc:
        print(f"[DOCS WARN] Docs Agent skipped due to error (fail-soft): {exc}")
        return 0

    if not plan.needs_update or not plan.updated_readme:
        print(f"[DOCS] No README update needed (prompt={prompt_ver}): {plan.change_summary}")
        return 0

    ok, reason = validate_readme_safely(original_readme, plan.updated_readme)
    if not ok:
        print(f"[DOCS GUARDRAIL] Rejected README update (fail-soft): {reason}")
        return 0

    README_PATH.write_text(plan.updated_readme.rstrip() + "\n", encoding="utf-8")
    print(
        f"[DOCS OK] README.md updated (model={llm.last_model}, prompt={prompt_ver}, "
        f"tokens={llm.tokens_used}): {plan.change_summary}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())