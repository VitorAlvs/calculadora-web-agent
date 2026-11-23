import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).parent))

from pydantic import BaseModel, Field
from run_agent import ResilientLLM, load_prompt

REPO_ROOT = Path(".").resolve()
PROMPT_PATH = REPO_ROOT / ".agent" / "prompts" / "reviewer_v1.md"
REVIEW_REPORT_PATH = Path(os.getenv("RUNNER_TEMP", str(REPO_ROOT))) / "review_report.md"


class ReviewVerdict(BaseModel):
    approved: bool = Field(description="True if the PR meets all requirements with no blocking issues")
    risk_level: Literal["low", "medium", "high"]
    summary: str = Field(min_length=15, description="Concise review verdict")
    findings: list[str] = Field(
        default_factory=list,
        description="List of specific issues or suggestions (empty if none)",
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


def main() -> int:
    issue_num = os.getenv("ISSUE_NUMBER", "0")
    issue_title = os.getenv("ISSUE_TITLE", "").strip()
    issue_body = os.getenv("ISSUE_BODY", "").strip()
    issue_author = os.getenv("ISSUE_AUTHOR", "").strip()

    diff = get_git_diff()
    if not diff:
        print("[REVIEWER] Empty diff — nothing to review.", file=sys.stderr)
        return 1

    prompt_ver, system_prompt = load_prompt(PROMPT_PATH)
    llm = ResilientLLM()

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"## Issue #{issue_num}: {issue_title}\n\n"
                f"{issue_body}\n\n"
                f"## Git Diff (`main...HEAD`)\n```diff\n{diff}\n```"
            ),
        },
    ]

    verdict = llm.call_structured(messages, ReviewVerdict, step=1)

    badge = "APPROVED" if verdict.approved else "CHANGES REQUESTED"
    findings_md = (
        "\n".join(f"- {item}" for item in verdict.findings)
        if verdict.findings
        else "- No blocking issues found."
    )
    ping = f"@{issue_author} — PR ready for your final merge approval." if (verdict.approved and issue_author) else ""

    report = (
        f"## Reviewer Agent Verdict: `{badge}`\n\n"
        f"- **Model:** `{llm.last_model}` | **Prompt:** `{prompt_ver}` | **Tokens:** {llm.tokens_used}\n"
        f"- **Risk level:** `{verdict.risk_level}`\n\n"
        f"### Summary\n{verdict.summary}\n\n"
        f"### Findings\n{findings_md}\n\n"
        f"{ping}\n"
    )
    REVIEW_REPORT_PATH.write_text(report, encoding="utf-8")

    gh_env = os.getenv("GITHUB_ENV")
    if gh_env:
        with open(gh_env, "a", encoding="utf-8") as f:
            f.write(f"REVIEW_APPROVED={'true' if verdict.approved else 'false'}\n")

    print(f"[REVIEWER] Verdict={badge} risk={verdict.risk_level} tokens={llm.tokens_used}")
    return 0


if __name__ == "__main__":
    sys.exit(main())