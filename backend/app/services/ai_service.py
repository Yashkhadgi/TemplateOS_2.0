"""
AI suggestion service (V1.3 Phase 4 — Member 2).

The FIRST TemplateOS AI feature: propose missing template fields from a
document's text using AWS Bedrock (Claude Sonnet) via the Anthropic SDK,
wrapped with instructor so the model's reply comes back as a VALIDATED
Pydantic object (FieldSuggestionList) — never hand-parsed JSON.

Rules (MD/features.md §10):
- Backend-only AI. The frontend calls FastAPI; only FastAPI calls Bedrock.
- Suggestions are PROPOSALS ONLY — this module never touches the database;
  the owner accepts them through the Phase 3 field endpoints (source="ai").
- Graceful degradation: anything missing (deps, region, credentials) or any
  provider failure raises AiUnavailableError, which the endpoint maps to
  503. The rest of the app keeps working without AI.

Diagnostics: every failure is logged with a WHY (classified cause + fix
hint) and a WHERE (the failing stage), so the uvicorn console shows exactly
what broke — the same information `scripts/verify_bedrock.py` reports.

Import safety: anthropic/instructor are imported INSIDE _build_client, so
importing this module (and booting the app, and running non-AI tests) works
even when the AI dependencies are not installed.
"""

import logging

from app.core.config import settings
from app.schemas.ai import FieldSuggestion, FieldSuggestionList
from app.services.docx_parser import VALID_KEY_PATTERN

logger = logging.getLogger(__name__)

# Cap the document excerpt fed to the model (token/cost control).
MAX_DOCUMENT_TEXT_CHARS = 6000

_SYSTEM_PROMPT = (
    "You help turn a document into a reusable template. Given the document "
    "text and the placeholders that already exist, suggest ADDITIONAL fields "
    "that should be captured. Prefer lowercase snake_case keys, meaningful "
    "labels, correct MVP types (text, textarea, date, number, list, "
    "signature), a sensible section, whether it is required, and an example "
    "value. Do NOT repeat existing keys. If the document already covers "
    "everything, return an empty list."
)


class AiUnavailableError(Exception):
    """AI (Bedrock) is not configured or the provider call failed."""


def _config_problem() -> str | None:
    """
    Return a human-readable description of the FIRST configuration problem,
    or None when AI could actually be called. Says exactly WHICH piece is
    missing (region, env credentials, profile credentials) so the 503
    response and scripts/verify_bedrock.py can tell the user what to fix.
    """
    if not settings.aws_region:
        return (
            "AWS_REGION is not set — leave it unset to keep AI off, or set "
            "it to your Bedrock region (e.g. ap-south-1)"
        )
    if not settings.bedrock_model_suggestions:
        return (
            "BEDROCK_MODEL_SUGGESTIONS is not set — set it in .env to the "
            "model / inference-profile id from the Bedrock console (Model "
            "access); there is no default model id in code"
        )
    import os

    if os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        return None
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        return None
    try:
        from boto3.session import Session

        if Session(region_name=settings.aws_region).get_credentials() is not None:
            return None
        return (
            "AWS_REGION is set but no AWS auth was found — set "
            "AWS_BEARER_TOKEN_BEDROCK (Bedrock long-term API key from the "
            "console) or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY in .env, "
            "or run 'aws configure' once"
        )
    except Exception as exc:
        return f"AWS_REGION is set but the credential chain check failed ({exc})"


def _status_error(exc: BaseException, _depth: int = 0):
    """
    Find the deepest exception in the chain carrying an HTTP status_code.
    instructor wraps provider errors (e.g. an AWS 403) in
    InstructorRetryException, so the wrapper's name alone would misclassify
    a permission failure as a schema-validation failure. Unwrap first.
    Returns None when no exception in the chain has a status.
    """
    if _depth > 4:
        return None
    if getattr(exc, "status_code", None) is not None:
        return exc
    for attr in ("last_exception", "__cause__"):
        nested = getattr(exc, attr, None)
        if isinstance(nested, BaseException):
            found = _status_error(nested, _depth + 1)
            if found is not None:
                return found
    return None


def _classify_ai_error(exc: Exception) -> str:
    """
    Map a provider/SDK exception to a human-readable WHY (what to fix).
    Classifies by exception name / HTTP status_code so no SDK imports are
    needed here — keeps the module import-safe without AI dependencies.
    Wrapped errors are unwrapped first: an InstructorRetryException around
    an AWS 403 is a PERMISSION problem, not a schema-validation problem.
    """
    name = type(exc).__name__

    # Unwrap instructor/SDK wrappers to the underlying provider error.
    underlying = _status_error(exc)
    if underlying is not None and underlying is not exc:
        return _classify_ai_error(underlying)

    status = getattr(exc, "status_code", None)

    if name == "InstructorRetryException":
        return (
            "the AI model returned output that failed schema validation "
            "after retries — retry the request; if it persists, report it"
        )
    if status == 400:
        aws_detail = str(exc).strip().replace("\n", " ")
        if len(aws_detail) > 220:
            aws_detail = aws_detail[:220] + "…"
        return (
            "AWS rejected the request (HTTP 400) — usually a malformed or "
            "unavailable model id: check BEDROCK_MODEL_SUGGESTIONS="
            f"'{settings.bedrock_model_suggestions}' in .env against the "
            "exact id shown in the Bedrock console (Model access)"
            + (f" [{aws_detail}]" if aws_detail else "")
        )
    if status == 401:
        return (
            "AWS credentials were rejected (HTTP 401) — your access keys "
            "are invalid or expired; rotate them in AWS IAM and update .env"
        )
    if status == 403:
        aws_detail = str(exc).strip().replace("\n", " ")
        if len(aws_detail) > 220:
            aws_detail = aws_detail[:220] + "…"
        return (
            "AWS denied the call (HTTP 403) — the API key or IAM user lacks "
            "permission for this model, or model access is not enabled in "
            "the Bedrock console for this region"
            + (f" [{aws_detail}]" if aws_detail else "")
        )
    if status == 404:
        return (
            "Bedrock model not found / access not enabled (HTTP 404) — "
            f"check BEDROCK_MODEL_SUGGESTIONS="
            f"'{settings.bedrock_model_suggestions}' and enable model "
            "access in the AWS Bedrock console (Model access -> Claude)"
        )
    if status == 429:
        return "Bedrock throttled the request (HTTP 429) — wait a moment and retry"
    if status is not None and status >= 500:
        return (
            f"AWS-side Bedrock error (HTTP {status}) — retry; if it "
            "persists, check the AWS health dashboard"
        )
    if name == "APITimeoutError":
        return (
            "the Bedrock call timed out — retry, or check network egress "
            "to bedrock-runtime.<region>.amazonaws.com"
        )
    if name == "APIConnectionError":
        return (
            "could not reach AWS Bedrock — network/DNS/firewall issue "
            "between this server and AWS"
        )
    if name in (
        "NoCredentialsError",
        "CredentialRetrievalError",
        "TokenRetrievalError",
    ):
        return (
            "AWS credentials disappeared mid-flight — re-run "
            "scripts/verify_bedrock.py to re-check the credential chain"
        )
    if name in ("ClientError", "BotoClientError"):
        return f"AWS SDK error: {exc}"
    return f"unexpected AI error ({name}): {exc}"


def _build_client():
    """
    Return an instructor-wrapped AnthropicBedrock client, or raise
    AiUnavailableError. Every failure mode (missing deps, missing region,
    unresolvable credentials, SDK construction error) funnels into
    AiUnavailableError so FastAPI never sees a raw 500.
    """
    problem = _config_problem()
    if problem is not None:
        logger.error(f"[ai] Bedrock NOT configured — WHY: {problem}")
        raise AiUnavailableError(f"AI is not configured: {problem}")
    try:
        import instructor
        from anthropic import AnthropicBedrock
    except ImportError as exc:
        logger.error(
            f"[ai] dependencies missing — WHY: {exc} (install with "
            "'pip install -r requirements.txt': anthropic[bedrock] + "
            "instructor)"
        )
        raise AiUnavailableError(
            "AI dependencies are not installed (anthropic/instructor)"
        ) from exc
    try:
        return instructor.from_anthropic(
            AnthropicBedrock(aws_region=settings.aws_region)
        )
    except Exception as exc:
        reason = _classify_ai_error(exc)
        logger.error(
            f"[ai] Bedrock client init failed — WHERE: "
            f"ai_service._build_client — WHY: {reason}"
        )
        logger.debug("[ai] traceback:", exc_info=True)
        raise AiUnavailableError(f"AI is currently unavailable: {reason}") from exc


def suggest_fields(
    document_text: str, existing_keys: list[str]
) -> list[FieldSuggestion]:
    """
    Ask Claude Sonnet on Bedrock for ADDITIONAL template fields and return
    the validated, deduplicated suggestions. Provider/dependency failures
    raise AiUnavailableError (the endpoint maps that to 503) and are logged
    with a classified WHY + the failing stage.
    """
    client = _build_client()

    existing = list(existing_keys)
    excerpt = document_text[:MAX_DOCUMENT_TEXT_CHARS]
    user_content = (
        "Existing placeholder keys (do NOT suggest these again):\n"
        f"{', '.join(existing) if existing else '(none)'}\n\n"
        "Document text:\n"
        f"{excerpt}"
    )

    try:
        result = client.messages.create(
            model=settings.bedrock_model_suggestions,
            max_tokens=settings.ai_max_output_tokens,
            system=_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_content},
            ],
            response_model=FieldSuggestionList,
        )
    except AiUnavailableError:
        raise
    except Exception as exc:
        reason = _classify_ai_error(exc)
        logger.error(
            f"[ai] field suggestion call failed — WHERE: "
            f"ai_service.suggest_fields -> Bedrock "
            f"(model={settings.bedrock_model_suggestions}) — WHY: {reason}"
        )
        logger.debug("[ai] traceback:", exc_info=True)
        raise AiUnavailableError(f"AI is currently unavailable: {reason}") from exc

    # instructor already validated the schema; still enforce the key rule
    # and dedupe against existing keys (and within the model's own reply).
    taken = set(existing)
    cleaned: list[FieldSuggestion] = []
    for suggestion in result.suggestions:
        if (
            not VALID_KEY_PATTERN.match(suggestion.field_name)
            or suggestion.field_name in taken
        ):
            continue
        taken.add(suggestion.field_name)
        cleaned.append(suggestion)
    return cleaned
