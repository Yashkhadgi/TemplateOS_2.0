"""
Verify the AI (AWS Bedrock) configuration — no database involved.

Usage (from backend/):
    python scripts/verify_bedrock.py           # config-only checks, no AWS calls
    python scripts/verify_bedrock.py --live    # ALSO make one tiny real Bedrock call

What it checks (in order):
  1. Settings resolve (.env present, required keys, AI values)
  2. Python dependencies (anthropic / instructor / boto3)
  3. AWS auth (Bedrock long-term API key -> env vars -> shared profile -> instance role)
  4. --live only: a real model invocation (validates auth AND
     console model access — the only way to know for sure)

Exit code 0 = everything it checked passed; 1 = something failed.
Failures print the same WHY text the API server logs on a 503.
"""

import argparse
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

PASS = "  [OK]  "
FAIL = "  [FAIL]"
SKIP = "  [SKIP]"

problems = 0


def report(ok: bool, message: str) -> None:
    global problems
    print(f"{PASS if ok else FAIL} {message}")
    if not ok:
        problems += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also make one tiny real Bedrock call (costs a few hundred tokens)",
    )
    args = parser.parse_args()

    print("=" * 66)
    print("TemplateOS — Bedrock AI configuration check")
    print("=" * 66)

    # ── 1. Settings ────────────────────────────────────────────────
    print("\n[1/4] Settings (app/core/config.py <- repository .env)")
    try:
        from app.core.config import settings
    except Exception as exc:
        report(False, f"Settings failed to load: {exc}")
        report(
            False,
            "Fix: copy .env.example to the repository root .env and set "
            "DATABASE_URL + JWT_SECRET_KEY first",
        )
        sys.exit(1)
    report(True, f"settings loaded (env={settings.app_env})")
    print(f"        AWS_REGION .................... {settings.aws_region!r}")
    print(
        f"        BEDROCK_MODEL_SUGGESTIONS ..... {settings.bedrock_model_suggestions!r}"
    )
    print(f"        AI_MAX_OUTPUT_TOKENS .......... {settings.ai_max_output_tokens}")
    if not settings.aws_region:
        print(
            f"{SKIP} AI is intentionally OFF (AWS_REGION unset) — the "
            "suggest-fields endpoint will return 503 by design"
        )

    # ── 2. Dependencies ────────────────────────────────────────────
    print("\n[2/4] Python dependencies")
    try:
        import anthropic

        report(
            True,
            f"anthropic {getattr(anthropic, '__version__', '?')} "
            f"(AnthropicBedrock available: {hasattr(anthropic, 'AnthropicBedrock')})",
        )
    except ImportError as exc:
        report(False, f"anthropic missing ({exc}) — pip install -r requirements.txt")
    try:
        import instructor

        report(
            True,
            f"instructor {getattr(instructor, '__version__', '?')}",
        )
    except ImportError as exc:
        report(False, f"instructor missing ({exc}) — pip install -r requirements.txt")
    try:
        import boto3

        report(True, f"boto3 {boto3.__version__}")
    except ImportError as exc:
        report(False, f"boto3 missing ({exc}) — pip install 'anthropic[bedrock]'")

    # ── 3. Credential chain ────────────────────────────────────────
    print("\n[3/4] AWS auth")
    from app.services.ai_service import _config_problem

    problem = _config_problem()
    if problem is None:
        import os

        if os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
            via = "Bedrock long-term API key (AWS_BEARER_TOKEN_BEDROCK)"
        elif os.environ.get("AWS_ACCESS_KEY_ID"):
            via = "environment variables (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)"
        else:
            via = "shared AWS profile / instance role (boto3 default chain)"
        report(True, f"credentials resolve via {via}")
    else:
        report(False, problem)

    if not args.live:
        if problem is None:
            print(
                "\nConfig-only check done. Run with --live to verify IAM "
                "permission + console model access with a real call."
            )
        print(f"\nResult: {'FAIL' if problems else 'OK'} ({problems} problem(s))")
        sys.exit(1 if problems else 0)

    # ── 4. Live call ───────────────────────────────────────────────
    print("\n[4/4] Live Bedrock call (--live)")
    from app.services import ai_service
    from app.services.ai_service import AiUnavailableError

    print(
        f"        calling model={settings.bedrock_model_suggestions!r} "
        "with a tiny probe document ..."
    )
    started = time.perf_counter()
    try:
        suggestions = ai_service.suggest_fields(
            "Invoice for services rendered to ACME Corp. Total due: $1500.",
            ["client_name"],
        )
    except AiUnavailableError as exc:
        elapsed = (time.perf_counter() - started) * 1000
        report(
            False,
            f"Bedrock call failed after {elapsed:.0f} ms — WHY: {exc}",
        )
        print(
            "        (the running API server logs the same WHY on every "
            "503 — see the uvicorn console)"
        )
        sys.exit(1)
    elapsed = (time.perf_counter() - started) * 1000
    report(
        True,
        f"model replied in {elapsed:.0f} ms with {len(suggestions)} "
        f"proposal(s) for the probe document",
    )
    for suggestion in suggestions[:3]:
        print(f"          - {suggestion.field_name} ({suggestion.field_type})")

    print(f"\nResult: {'FAIL' if problems else 'OK'} ({problems} problem(s))")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
