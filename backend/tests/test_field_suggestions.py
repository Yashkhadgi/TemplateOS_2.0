"""
Schema + integration tests for V1.3 Phase 4 AI field suggestions.
Member 3 — Database / Integration Developer

Layers:
1. Schemas: FieldSuggestion rejects invalid keys ("Bad Key") and invalid
   types ("dropdown"); FieldSuggestionList is the instructor
   response_model wrapper; SuggestFieldsResponse is the endpoint
   envelope; AiGenerationRead reads ORM rows (from_attributes).
2. Accept path: a suggestion accepted through the Phase 3 field
   endpoints (POST create + PUT sync) is persisted with source="ai".
3. Endpoint contract — POST /templates/{id}/suggest-fields, with the AI
   provider MOCKED (never real Bedrock). These tests activate once
   Member 2 ships app/services/ai_service.py + the route; until then
   they skip cleanly:
   - mocked success returns the suggestions, writes NO template_fields,
     and logs exactly ONE ai_generations row (status="success");
   - mocked AiUnavailableError returns 503 and logs a status="error" row.
"""

import io
import os
from datetime import datetime

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-auth-tests"
)
# No model id is hardcoded in app code — tests provide one like .env would.
os.environ.setdefault("BEDROCK_MODEL_SUGGESTIONS", "test-model-id")

# Single test-wide constant (matches the env value above) so no real Bedrock
# model id is hardcoded anywhere in the test suite.
TEST_MODEL_ID = "test-model-id"

from app.crud.ai_generation_crud import log_ai_generation
from app.crud.template_field_crud import get_fields_by_template
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.ai_generation import AiGeneration
from app.models.template import Template
from app.models.user import User
from app.schemas.ai import (
    AiGenerationRead,
    FieldSuggestion,
    FieldSuggestionList,
    SuggestFieldsResponse,
)
from app.services.storage_service import storage_service

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_get_db():
    with TestSession() as db:
        yield db


client = TestClient(app)

OWNER_EMAIL = "suggest_owner@example.com"

# Member 2's ai_service + suggest-fields route are not shipped yet — probe
# for them at import time and skip the endpoint tests until they land.
try:
    import app.services.ai_service as ai_service_module

    AiUnavailableError = getattr(ai_service_module, "AiUnavailableError", None)
except Exception:  # pragma: no cover - depends on Member 2's module
    ai_service_module = None
    AiUnavailableError = None

SUGGEST_ROUTE_PATH = next(
    (
        route.path
        for route in app.routes
        if getattr(route, "path", "").rstrip("/").endswith("suggest-fields")
    ),
    None,
)

requires_suggest_endpoint = pytest.mark.skipif(
    ai_service_module is None or SUGGEST_ROUTE_PATH is None,
    reason="Member 2's ai_service / suggest-fields endpoint is not shipped yet",
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    old = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if old is not None:
        app.dependency_overrides[get_db] = old
    else:
        app.dependency_overrides.pop(get_db, None)


def _signup_and_login(email: str, full_name: str) -> str:
    client.post(
        "/api/v1/auth/signup",
        json={"full_name": full_name, "email": email, "password": "strong-password"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-password"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


@pytest.fixture(scope="module")
def owner_token(setup_db):
    return _signup_and_login(OWNER_EMAIL, "Suggest Owner")


@pytest.fixture(scope="module")
def owner_id(owner_token) -> int:
    with TestSession() as session:
        owner = session.execute(
            select(User).where(User.email == OWNER_EMAIL)
        ).scalar_one()
        return owner.id


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _make_template(name: str, owner_id: int, with_file: bool = False) -> int:
    file_kwargs = {}
    if with_file:
        stored = storage_service.save_bytes(
            "templates_original",
            f"{name.lower().replace(' ', '-')}.docx",
            _make_docx_bytes("Meeting minutes for {{project_name}}."),
        )
        file_kwargs = {
            "original_file_path": stored.path,
            "original_filename": stored.filename,
            "file_size_bytes": stored.size_bytes,
            "file_extension": ".docx",
        }
    with TestSession() as session:
        template = Template(
            name=name,
            category="mom",
            visibility="private",
            uploaded_by=owner_id,
            status="placeholder_detected",
            **file_kwargs,
        )
        session.add(template)
        session.commit()
        session.refresh(template)
        return template.id


# ── 1. Schemas ──────────────────────────────────────────────────────


def test_field_suggestion_accepts_valid_shape():
    suggestion = FieldSuggestion(
        field_name="meeting_date",
        field_label="Meeting Date",
        field_type="date",
        section="Details",
        is_required=True,
        example_value="2026-09-10",
        reason="Minutes need the meeting date",
    )
    assert suggestion.field_name == "meeting_date"
    assert suggestion.field_type == "date"
    assert suggestion.is_required is True


def test_field_suggestion_rejects_invalid_key():
    with pytest.raises(ValidationError):
        FieldSuggestion(field_name="Bad Key", field_type="text")


def test_field_suggestion_rejects_invalid_type():
    with pytest.raises(ValidationError):
        FieldSuggestion(field_name="ok_key", field_type="dropdown")


def test_field_suggestion_defaults():
    suggestion = FieldSuggestion(field_name="attendees")
    assert suggestion.field_type == "text"
    assert suggestion.is_required is True
    assert suggestion.section is None
    assert suggestion.reason is None


def test_field_suggestion_list_wraps_suggestions():
    payload = FieldSuggestionList(
        suggestions=[
            FieldSuggestion(field_name="meeting_date", field_type="date"),
            FieldSuggestion(field_name="attendees", field_type="list"),
        ]
    )
    assert [item.field_name for item in payload.suggestions] == [
        "meeting_date",
        "attendees",
    ]
    assert FieldSuggestionList().suggestions == []


def test_suggest_fields_response_envelope():
    response = SuggestFieldsResponse(
        template_id=7,
        model=TEST_MODEL_ID,
        existing_count=2,
        suggestion_count=1,
        suggestions=[FieldSuggestion(field_name="meeting_date", field_type="date")],
    )
    assert response.template_id == 7
    assert response.suggestion_count == len(response.suggestions) == 1
    assert response.existing_count == 2


def test_ai_generation_read_from_attributes(owner_id):
    with TestSession() as session:
        template = Template(
            name="AiRead Template",
            category="mom",
            visibility="private",
            uploaded_by=owner_id,
            status="placeholder_detected",
        )
        session.add(template)
        session.commit()

        row = log_ai_generation(
            session,
            action_type="suggest_fields",
            model=TEST_MODEL_ID,
            template_id=template.id,
            created_by=owner_id,
            suggestions_count=4,
        )

        read = AiGenerationRead.model_validate(row)
        assert read.id == row.id
        assert read.action_type == "suggest_fields"
        assert read.model == TEST_MODEL_ID
        assert read.template_id == template.id
        assert read.field_key is None
        assert read.status == "success"
        assert read.suggestions_count == 4
        assert isinstance(read.created_at, datetime)


# ── 2. Accept path: suggestion -> template_field with source="ai" ───


def test_accept_suggestion_via_create_endpoint_sets_source_ai(owner_token, owner_id):
    template_id = _make_template("Accept Create Template", owner_id)
    payload = {
        "field_name": "meeting_date",
        "field_label": "Meeting Date",
        "field_type": "date",
        "section": "Details",
        "is_required": True,
        "example_value": "2026-09-10",
        "source": "ai",
    }
    response = client.post(
        f"/api/v1/templates/{template_id}/fields",
        json=payload,
        headers=_auth(owner_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source"] == "ai"

    with TestSession() as session:
        fields = get_fields_by_template(session, template_id)
        assert [field.field_name for field in fields] == ["meeting_date"]
        assert fields[0].source == "ai"


def test_accept_suggestion_via_sync_endpoint_sets_source_ai(owner_token, owner_id):
    template_id = _make_template("Accept Sync Template", owner_id)
    payload = {
        "fields": [
            {
                "field_name": "attendees",
                "field_label": "Attendees",
                "field_type": "list",
                "source": "ai",
            }
        ]
    }
    response = client.put(
        f"/api/v1/templates/{template_id}/fields",
        json=payload,
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()[0]["source"] == "ai"

    with TestSession() as session:
        fields = get_fields_by_template(session, template_id)
        assert fields[0].field_name == "attendees"
        assert fields[0].source == "ai"


def test_field_created_without_source_defaults_detected(owner_token, owner_id):
    template_id = _make_template("Default Source Template", owner_id)
    response = client.post(
        f"/api/v1/templates/{template_id}/fields",
        json={"field_name": "owner_note"},
        headers=_auth(owner_token),
    )
    assert response.status_code == 201, response.text
    # Phase 3 default provenance is untouched by Phase 4.
    assert response.json()["source"] == "detected"


# ── 3. Endpoint contract (mocked AI — never real Bedrock) ───────────


@requires_suggest_endpoint
def test_suggest_fields_success_returns_suggestions_and_logs_one_row(
    monkeypatch, owner_token, owner_id
):
    template_id = _make_template("Suggest Source Template", owner_id, with_file=True)
    fixed_suggestions = [
        FieldSuggestion(
            field_name="meeting_date",
            field_label="Meeting Date",
            field_type="date",
            section="Details",
            is_required=True,
            example_value="2026-09-10",
            reason="Minutes reference the meeting date",
        ),
        FieldSuggestion(
            field_name="attendees",
            field_label="Attendees",
            field_type="list",
            section="Details",
            is_required=False,
            example_value="Alice, Bob",
            reason="Who attended the meeting",
        ),
    ]
    seen: dict[str, object] = {}

    def fake_suggest_fields(document_text: str, existing_keys: list[str]):
        seen["document_text"] = document_text
        seen["existing_keys"] = list(existing_keys)
        return list(fixed_suggestions)

    monkeypatch.setattr(ai_service_module, "suggest_fields", fake_suggest_fields)

    response = client.post(
        SUGGEST_ROUTE_PATH.format(template_id=template_id),
        headers=_auth(owner_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["template_id"] == template_id
    assert body["model"]
    assert body["existing_count"] == 0
    assert body["suggestion_count"] == 2
    assert [item["field_name"] for item in body["suggestions"]] == [
        "meeting_date",
        "attendees",
    ]
    assert seen["document_text"]  # the endpoint fed it document text

    with TestSession() as session:
        # Proposals only: NOTHING is persisted as template_fields.
        assert get_fields_by_template(session, template_id) == []
        # Exactly ONE audit row per AI call, status success.
        rows = (
            session.execute(
                select(AiGeneration).where(AiGeneration.template_id == template_id)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].action_type == "suggest_fields"
        assert rows[0].status == "success"
        assert rows[0].created_by == owner_id
        assert rows[0].suggestions_count == 2


@requires_suggest_endpoint
def test_suggest_fields_unavailable_returns_503_and_logs_error_row(
    monkeypatch, owner_token, owner_id
):
    if AiUnavailableError is None:
        pytest.skip("ai_service.AiUnavailableError is not available yet")

    template_id = _make_template("Suggest Error Template", owner_id, with_file=True)

    def unavailable(document_text: str, existing_keys: list[str]):
        raise AiUnavailableError("AI is not configured")

    monkeypatch.setattr(ai_service_module, "suggest_fields", unavailable)

    response = client.post(
        SUGGEST_ROUTE_PATH.format(template_id=template_id),
        headers=_auth(owner_token),
    )
    assert response.status_code == 503
    assert "ai" in response.json()["detail"].lower()

    with TestSession() as session:
        rows = (
            session.execute(
                select(AiGeneration).where(AiGeneration.template_id == template_id)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].status == "error"
        assert rows[0].action_type == "suggest_fields"
