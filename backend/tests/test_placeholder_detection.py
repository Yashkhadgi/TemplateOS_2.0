"""
Integration tests for placeholder detection persistence.
V1.3 Phase 1 — Member 3

Two layers:

1. Persistence-flow tests (run now): simulate exactly what Member 2's
   detection endpoint will do with a DetectionResult — bulk-create valid
   fields once, guard idempotency with field_exists, replace on force via
   delete_fields_by_template. Invalid names never reach the CRUD layer.

2. Endpoint tests (skip until Member 2's routes exist): POST
   /api/v1/templates/{id}/detect-placeholders and GET /{id}/fields against
   real uploaded DOCX fixtures. The skips lift automatically once the
   detection API lands, at which point these tests verify the full contract:
   ordered persistence, duplicate collapse, invalid-name exclusion,
   idempotency, force re-detect, owner-only 403, split-across-runs parity,
   and no-500 on malformed tokens.
"""

import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-auth-tests"
)

from app.crud.template_field_crud import (
    bulk_create_fields,
    delete_fields_by_template,
    field_exists,
    get_fields_by_template,
)
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.template import Template
from app.models.template_field import TemplateField
from app.schemas.template_field import TemplateFieldCreate

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


# --- minimal DOCX fixtures (pure stdlib) ------------------------------------
# A DOCX is a zip; python-docx only needs [Content_Types].xml, _rels/.rels,
# and word/document.xml to open the document.


def _run(text: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'


def _build_docx(body_xml: str) -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p>{body_xml}</w:p></w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


# Clean template: employee_name appears twice (duplicate), start_date once,
# and amount is split across two runs (parity check). No malformed tokens.
CLEAN_DOCX = _build_docx(
    _run("Notice for {{employee_name}} dated {{start_date}}. ")
    + _run("Served to {{employee_name}}. ")
    + _run("Total {{amo")
    + _run("unt}} due.")
)

# Same as clean, plus one malformed token Jinja cannot parse.
MALFORMED_DOCX = _build_docx(
    _run("Notice for {{employee_name}} dated {{start_date}}. ")
    + _run("Served to {{employee_name}}. ")
    + _run("Total {{amo")
    + _run("unt}} due. ")
    + _run("Signed {{Bad Name}}.")
)

# The valid field set a detection run over either fixture should persist,
# in first-seen order (duplicates already collapsed by the parser).
EXPECTED_VALID_FIELDS = ["employee_name", "start_date", "amount"]


# --- API helpers --------------------------------------------------------------


def _signup_and_login(email: str, full_name: str) -> str:
    client.post(
        "/api/v1/auth/signup",
        json={"full_name": full_name, "email": email, "password": "strong-password"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-password"},
    )
    return login.json()["access_token"]


@pytest.fixture(scope="module")
def owner_token():
    return _signup_and_login("detect_owner@example.com", "Detection Owner")


@pytest.fixture(scope="module")
def other_token():
    return _signup_and_login("detect_other@example.com", "Detection Other")


def _upload_template(token: str, name: str, docx_bytes: bytes) -> dict:
    files = {
        "file": (
            "template.docx",
            io.BytesIO(docx_bytes),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {"name": name, "category": "notice", "visibility": "private"}
    response = client.post(
        "/api/v1/templates/upload",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, f"Upload failed: {response.json()}"
    return response.json()


def _persisted_field_names(template_id: int) -> list[str]:
    with TestSession() as db:
        rows = get_fields_by_template(db, template_id)
        return [row.field_name for row in rows]


def _persisted_field_count(template_id: int) -> int:
    with TestSession() as db:
        return len(get_fields_by_template(db, template_id))


# --- 1. Persistence-flow tests (no endpoint required) ------------------------


def test_detection_flow_persists_valid_fields_once():
    """Simulates the endpoint's first run: create the valid fields once."""
    with TestSession() as db:
        template = Template(
            name="Flow Once",
            category="notice",
            visibility="private",
            uploaded_by=1,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        template_id = template.id

    # What Member 2's service produces for the valid set (humanized labels,
    # text type, required, first-seen order) handed to Member 3's CRUD:
    payloads = [
        TemplateFieldCreate(
            field_name="employee_name",
            field_label="Employee Name",
            display_order=0,
        ),
        TemplateFieldCreate(
            field_name="start_date",
            field_label="Start Date",
            display_order=1,
        ),
        TemplateFieldCreate(
            field_name="amount",
            field_label="Amount",
            display_order=2,
        ),
    ]
    with TestSession() as db:
        rows = bulk_create_fields(db, template_id, payloads)
        assert [r.field_name for r in rows] == EXPECTED_VALID_FIELDS
        assert all(r.field_type == "text" for r in rows)
        assert all(r.is_required for r in rows)
        assert all(r.field_label is not None for r in rows)

    assert _persisted_field_names(template_id) == EXPECTED_VALID_FIELDS

    # Second run is idempotent: guarded by field_exists, nothing is re-created.
    with TestSession() as db:
        assert all(
            field_exists(db, template_id, name) for name in EXPECTED_VALID_FIELDS
        )
    assert _persisted_field_count(template_id) == 3


def test_detection_flow_force_rerun_replaces_fields():
    """Simulates force re-detect: delete, then bulk-create the fresh set."""
    with TestSession() as db:
        template = Template(
            name="Flow Force",
            category="notice",
            visibility="private",
            uploaded_by=1,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        template_id = template.id

    with TestSession() as db:
        bulk_create_fields(
            db,
            template_id,
            [
                TemplateFieldCreate(field_name="stale_field", display_order=0),
            ],
        )
    assert _persisted_field_names(template_id) == ["stale_field"]

    with TestSession() as db:
        deleted = delete_fields_by_template(db, template_id)
        assert deleted == 1
        bulk_create_fields(
            db,
            template_id,
            [
                TemplateFieldCreate(field_name="employee_name", display_order=0),
                TemplateFieldCreate(field_name="amount", display_order=1),
            ],
        )

    assert _persisted_field_names(template_id) == ["employee_name", "amount"]


def test_detection_flow_invalid_names_never_reach_persistence():
    """Malformed tokens ({{Bad Name}}) are filtered out by the parser and
    never handed to bulk_create — the table only ever holds valid keys."""
    with TestSession() as db:
        template = Template(
            name="Flow Invalid",
            category="notice",
            visibility="private",
            uploaded_by=1,
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        template_id = template.id

    # The parser's valid_fields for MALFORMED_DOCX (fallback path) are the
    # same three keys; "Bad Name" only exists in the warnings list.
    with TestSession() as db:
        bulk_create_fields(
            db,
            template_id,
            [
                TemplateFieldCreate(field_name="employee_name", display_order=0),
                TemplateFieldCreate(field_name="start_date", display_order=1),
                TemplateFieldCreate(field_name="amount", display_order=2),
            ],
        )

    names = _persisted_field_names(template_id)
    assert names == EXPECTED_VALID_FIELDS
    assert "bad_name" not in names
    with TestSession() as db:
        assert not field_exists(db, template_id, "Bad Name")


# --- 2. Endpoint tests (activate once Member 2's routes exist) ----------------

ROUTE_PATHS = {getattr(route, "path", "") for route in app.routes}
DETECT_ENDPOINT_MISSING = not any(
    p.endswith("/detect-placeholders") for p in ROUTE_PATHS
)
FIELDS_ENDPOINT_MISSING = not any(p.endswith("/fields") for p in ROUTE_PATHS)

requires_detect_endpoint = pytest.mark.skipif(
    DETECT_ENDPOINT_MISSING,
    reason="POST /templates/{id}/detect-placeholders not implemented yet (Member 2, V1.3 Phase 1)",
)
requires_fields_endpoint = pytest.mark.skipif(
    FIELDS_ENDPOINT_MISSING,
    reason="GET /templates/{id}/fields not implemented yet (Member 2, V1.3 Phase 1)",
)


@requires_detect_endpoint
def test_detect_placeholders_persists_ordered_fields(owner_token):
    template = _upload_template(owner_token, "Detection Clean", CLEAN_DOCX)
    response = client.post(
        f"/api/v1/templates/{template['id']}/detect-placeholders",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200, response.json()
    body = response.json()

    assert body["status"] == "placeholder_detected"
    assert body["already_detected"] is False
    assert [f["field_name"] for f in body["detected_fields"]] == EXPECTED_VALID_FIELDS

    # First-seen order and detection defaults.
    assert [f["display_order"] for f in body["detected_fields"]] == [0, 1, 2]
    assert all(f["field_type"] == "text" for f in body["detected_fields"])
    assert all(f["is_required"] is True for f in body["detected_fields"])

    # Duplicates collapse to one field and are reported.
    assert body["warnings"]["duplicates"] == [{"key": "employee_name", "count": 2}]
    assert body["warnings"]["parse_error"] is None

    assert body["summary"] == {
        "total_matches": 4,
        "unique_valid": 3,
        "invalid_count": 0,
        "duplicate_count": 1,
    }

    # Rows really persisted, in order.
    assert _persisted_field_names(template["id"]) == EXPECTED_VALID_FIELDS


@requires_detect_endpoint
def test_detect_placeholders_is_idempotent(owner_token):
    template = _upload_template(owner_token, "Detection Idempotent", CLEAN_DOCX)
    headers = {"Authorization": f"Bearer {owner_token}"}
    first = client.post(
        f"/api/v1/templates/{template['id']}/detect-placeholders", headers=headers
    )
    assert first.status_code == 200
    assert first.json()["already_detected"] is False

    second = client.post(
        f"/api/v1/templates/{template['id']}/detect-placeholders", headers=headers
    )
    assert second.status_code == 200
    assert second.json()["already_detected"] is True
    assert [
        f["field_name"] for f in second.json()["detected_fields"]
    ] == EXPECTED_VALID_FIELDS

    # No duplicate rows were created.
    assert _persisted_field_count(template["id"]) == 3


@requires_detect_endpoint
def test_detect_placeholders_force_replaces_fields(owner_token):
    template = _upload_template(owner_token, "Detection Force", CLEAN_DOCX)
    headers = {"Authorization": f"Bearer {owner_token}"}
    first = client.post(
        f"/api/v1/templates/{template['id']}/detect-placeholders", headers=headers
    )
    assert first.status_code == 200

    forced = client.post(
        f"/api/v1/templates/{template['id']}/detect-placeholders?force=true",
        headers=headers,
    )
    assert forced.status_code == 200
    assert [
        f["field_name"] for f in forced.json()["detected_fields"]
    ] == EXPECTED_VALID_FIELDS
    assert _persisted_field_count(template["id"]) == 3
    assert _persisted_field_names(template["id"]) == EXPECTED_VALID_FIELDS


@requires_detect_endpoint
def test_detect_placeholders_reports_invalid_names_without_500(owner_token):
    template = _upload_template(owner_token, "Detection Malformed", MALFORMED_DOCX)
    response = client.post(
        f"/api/v1/templates/{template['id']}/detect-placeholders",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    # A malformed token must never produce a 500.
    assert response.status_code == 200, response.json()
    body = response.json()

    # The invalid token is reported with a suggested key...
    invalid = body["warnings"]["invalid_names"]
    assert len(invalid) == 1
    assert invalid[0]["raw"] == "Bad Name"
    assert invalid[0]["suggested_key"] == "bad_name"
    assert invalid[0]["count"] == 1
    assert invalid[0]["reason"]

    # ...docxtpl could not parse the template (Jinja rejects "Bad Name")...
    assert body["warnings"]["parse_error"] is not None

    # ...and the regex fallback still persisted the valid fields.
    assert [f["field_name"] for f in body["detected_fields"]] == EXPECTED_VALID_FIELDS
    assert _persisted_field_names(template["id"]) == EXPECTED_VALID_FIELDS

    assert body["summary"]["invalid_count"] == 1
    assert body["summary"]["total_matches"] == 5


@requires_detect_endpoint
def test_detect_placeholders_is_owner_only(owner_token, other_token):
    template = _upload_template(owner_token, "Detection Private", CLEAN_DOCX)
    response = client.post(
        f"/api/v1/templates/{template['id']}/detect-placeholders",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 403
    assert _persisted_field_count(template["id"]) == 0


@requires_detect_endpoint
def test_detect_placeholders_template_not_found(owner_token):
    response = client.post(
        "/api/v1/templates/999999/detect-placeholders",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 404


@requires_fields_endpoint
def test_get_fields_returns_ordered_list(owner_token):
    template = _upload_template(owner_token, "Detection Fields Read", CLEAN_DOCX)
    detect = client.post(
        f"/api/v1/templates/{template['id']}/detect-placeholders",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert detect.status_code == 200

    response = client.get(
        f"/api/v1/templates/{template['id']}/fields",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200
    assert [f["field_name"] for f in response.json()] == EXPECTED_VALID_FIELDS


@requires_fields_endpoint
def test_get_fields_enforces_view_access(owner_token, other_token):
    template = _upload_template(owner_token, "Detection Fields Access", CLEAN_DOCX)
    detect = client.post(
        f"/api/v1/templates/{template['id']}/detect-placeholders",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert detect.status_code == 200

    # Private template: a non-owner without view access gets 403.
    response = client.get(
        f"/api/v1/templates/{template['id']}/fields",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 403
