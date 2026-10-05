"""
API tests for the V1.3 Phase 3 field-editor endpoints (Member 2).

Definition of Done coverage:
- POST/PATCH/DELETE /templates/{id}/fields[...] + PUT /fields/reorder +
  PUT /fields (bulk sync) exist and are owner-only.
- Locked templates reject writes (403); duplicate key -> 409; invalid
  field_type -> 422; bad reorder set -> 422; duplicate-in-payload /
  foreign id -> 422; cross-item name swap -> 409.
- display_order stays contiguous 0..n-1 after every operation.
- Bulk PUT /fields syncs (create/update/delete-by-omission), advances
  status to field_configured (forward-only, gated on >=1 field), and
  returns the fresh ordered set.
- Reads stay viewer-accessible (public template) while writes do not.
- Route ordering: PUT /fields/reorder resolves to the reorder route
  (proven by its 200/422/403 responses, not a field_id 422).
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-that-is-long-enough-for-auth-tests"
)

from app.crud.template_field_crud import create_field
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.template import Template
from app.models.user import User
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

OWNER_EMAIL = "field_api_owner@example.com"
STRANGER_EMAIL = "field_api_stranger@example.com"


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
    return _signup_and_login(OWNER_EMAIL, "Field API Owner")


@pytest.fixture(scope="module")
def stranger_token(setup_db):
    return _signup_and_login(STRANGER_EMAIL, "Field API Stranger")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_template(
    name: str, status: str = "placeholder_detected", visibility: str = "private"
) -> int:
    with TestSession() as session:
        owner = session.execute(
            select(User).where(User.email == OWNER_EMAIL)
        ).scalar_one()
        template = Template(
            name=name,
            category="mom",
            visibility=visibility,
            uploaded_by=owner.id,
            status=status,
        )
        session.add(template)
        session.commit()
        session.refresh(template)
        return template.id


def _make_field(template_id: int, name: str, **overrides) -> int:
    with TestSession() as session:
        field = create_field(
            session, template_id, TemplateFieldCreate(field_name=name, **overrides)
        )
        return field.id


def _api_fields(token: str, template_id: int) -> list[dict]:
    response = client.get(
        f"/api/v1/templates/{template_id}/fields", headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


def _db_status(template_id: int) -> str:
    with TestSession() as session:
        return session.get(Template, template_id).status


# ── POST /{id}/fields — create ────────────────────────────────────


def test_create_field_appends_in_order(owner_token):
    template_id = _make_template("API Create Order")

    first = client.post(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={"field_name": "meeting_title", "field_label": "Meeting Title"},
    )
    assert first.status_code == 201, first.text
    assert first.json()["field_name"] == "meeting_title"
    assert first.json()["display_order"] == 0

    second = client.post(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={"field_name": "meeting_date", "field_type": "date"},
    )
    assert second.status_code == 201
    assert second.json()["display_order"] == 1

    fields = _api_fields(owner_token, template_id)
    assert [f["field_name"] for f in fields] == ["meeting_title", "meeting_date"]
    assert [f["display_order"] for f in fields] == [0, 1]


def test_create_field_404_missing_template(owner_token):
    response = client.post(
        "/api/v1/templates/999999/fields",
        headers=_auth(owner_token),
        json={"field_name": "ghost"},
    )
    assert response.status_code == 404


def test_create_field_403_for_stranger(stranger_token, owner_token):
    template_id = _make_template("API Create Not Owner")
    response = client.post(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(stranger_token),
        json={"field_name": "sneaky"},
    )
    assert response.status_code == 403
    assert _api_fields(owner_token, template_id) == []


def test_create_field_409_duplicate_key(owner_token):
    template_id = _make_template("API Create Duplicate")
    _make_field(template_id, "meeting_title")

    response = client.post(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={"field_name": "meeting_title"},
    )
    assert response.status_code == 409


def test_create_field_422_invalid_type(owner_token):
    template_id = _make_template("API Create Bad Type")
    response = client.post(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={"field_name": "bad_type", "field_type": "dropdown"},
    )
    assert response.status_code == 422


def test_create_field_explicit_order_renumbered_contiguous(owner_token):
    template_id = _make_template("API Create Explicit Order")
    _make_field(template_id, "alpha")
    _make_field(template_id, "beta")

    response = client.post(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={"field_name": "gamma", "display_order": 5},
    )
    assert response.status_code == 201, response.text

    fields = _api_fields(owner_token, template_id)
    assert [f["field_name"] for f in fields] == ["alpha", "beta", "gamma"]
    assert [f["display_order"] for f in fields] == [0, 1, 2]


# ── PATCH /{id}/fields/{field_id} — partial update ────────────────


def test_update_field_partial(owner_token):
    template_id = _make_template("API Update Partial")
    field_id = _make_field(
        template_id, "meeting_title", field_label="Old Label", field_type="text"
    )

    response = client.patch(
        f"/api/v1/templates/{template_id}/fields/{field_id}",
        headers=_auth(owner_token),
        json={"field_label": "New Label", "is_required": False},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["field_label"] == "New Label"
    assert body["is_required"] is False
    # Untouched attributes keep their values.
    assert body["field_type"] == "text"


def test_update_field_404_missing_or_wrong_template(owner_token):
    template_id = _make_template("API Update 404 Home")
    other_id = _make_template("API Update 404 Other")
    foreign_field = _make_field(other_id, "foreign_key")

    missing = client.patch(
        f"/api/v1/templates/{template_id}/fields/999999",
        headers=_auth(owner_token),
        json={"field_label": "x"},
    )
    assert missing.status_code == 404

    wrong = client.patch(
        f"/api/v1/templates/{template_id}/fields/{foreign_field}",
        headers=_auth(owner_token),
        json={"field_label": "x"},
    )
    assert wrong.status_code == 404


def test_update_field_409_rename_collision(owner_token):
    template_id = _make_template("API Update Collision")
    _make_field(template_id, "meeting_title")
    other = _make_field(template_id, "meeting_date")

    response = client.patch(
        f"/api/v1/templates/{template_id}/fields/{other}",
        headers=_auth(owner_token),
        json={"field_name": "meeting_title"},
    )
    assert response.status_code == 409


def test_update_field_422_invalid_type(owner_token):
    template_id = _make_template("API Update Bad Type")
    field_id = _make_field(template_id, "ok_key")

    response = client.patch(
        f"/api/v1/templates/{template_id}/fields/{field_id}",
        headers=_auth(owner_token),
        json={"field_type": "dropdown"},
    )
    assert response.status_code == 422


def test_update_field_403_for_stranger(stranger_token, owner_token):
    template_id = _make_template("API Update Not Owner")
    field_id = _make_field(template_id, "private_key")

    response = client.patch(
        f"/api/v1/templates/{template_id}/fields/{field_id}",
        headers=_auth(stranger_token),
        json={"field_label": "hijacked"},
    )
    assert response.status_code == 403


# ── DELETE /{id}/fields/{field_id} — delete + reindex ─────────────


def test_delete_field_reindexes_remaining(owner_token):
    template_id = _make_template("API Delete Reindex")
    _make_field(template_id, "alpha")
    beta = _make_field(template_id, "beta")
    _make_field(template_id, "gamma")

    response = client.delete(
        f"/api/v1/templates/{template_id}/fields/{beta}",
        headers=_auth(owner_token),
    )
    assert response.status_code == 204

    fields = _api_fields(owner_token, template_id)
    assert [f["field_name"] for f in fields] == ["alpha", "gamma"]
    assert [f["display_order"] for f in fields] == [0, 1]


def test_delete_field_404_missing_or_wrong_template(owner_token):
    template_id = _make_template("API Delete 404 Home")
    other_id = _make_template("API Delete 404 Other")
    foreign_field = _make_field(other_id, "foreign_key")

    missing = client.delete(
        f"/api/v1/templates/{template_id}/fields/999999",
        headers=_auth(owner_token),
    )
    assert missing.status_code == 404

    wrong = client.delete(
        f"/api/v1/templates/{template_id}/fields/{foreign_field}",
        headers=_auth(owner_token),
    )
    assert wrong.status_code == 404


def test_delete_field_403_for_stranger(stranger_token, owner_token):
    template_id = _make_template("API Delete Not Owner")
    field_id = _make_field(template_id, "private_key")

    response = client.delete(
        f"/api/v1/templates/{template_id}/fields/{field_id}",
        headers=_auth(stranger_token),
    )
    assert response.status_code == 403


# ── PUT /{id}/fields/reorder — explicit reorder ───────────────────


def test_reorder_fields_returns_fresh_order(owner_token):
    template_id = _make_template("API Reorder OK")
    alpha = _make_field(template_id, "alpha")
    beta = _make_field(template_id, "beta")
    gamma = _make_field(template_id, "gamma")

    response = client.put(
        f"/api/v1/templates/{template_id}/fields/reorder",
        headers=_auth(owner_token),
        json={"ordered_ids": [gamma, alpha, beta]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [f["field_name"] for f in body] == ["gamma", "alpha", "beta"]
    assert [f["display_order"] for f in body] == [0, 1, 2]

    # Persisted: the plain GET reflects the same order.
    fields = _api_fields(owner_token, template_id)
    assert [f["field_name"] for f in fields] == ["gamma", "alpha", "beta"]


def test_reorder_fields_422_bad_permutation(owner_token):
    template_id = _make_template("API Reorder Bad")
    alpha = _make_field(template_id, "alpha")
    _make_field(template_id, "beta")

    missing = client.put(
        f"/api/v1/templates/{template_id}/fields/reorder",
        headers=_auth(owner_token),
        json={"ordered_ids": [alpha]},
    )
    assert missing.status_code == 422

    unknown = client.put(
        f"/api/v1/templates/{template_id}/fields/reorder",
        headers=_auth(owner_token),
        json={"ordered_ids": [alpha, 999999]},
    )
    assert unknown.status_code == 422

    # Nothing changed on failure.
    fields = _api_fields(owner_token, template_id)
    assert [f["field_name"] for f in fields] == ["alpha", "beta"]
    assert [f["display_order"] for f in fields] == [0, 1]


def test_reorder_fields_403_for_stranger(stranger_token, owner_token):
    template_id = _make_template("API Reorder Not Owner")
    alpha = _make_field(template_id, "alpha")

    response = client.put(
        f"/api/v1/templates/{template_id}/fields/reorder",
        headers=_auth(stranger_token),
        json={"ordered_ids": [alpha]},
    )
    assert response.status_code == 403


# ── PUT /{id}/fields — bulk sync (full-sync semantics) ────────────


def test_sync_full_semantics_and_status_advance(owner_token):
    template_id = _make_template("API Sync Mixed")
    alpha = _make_field(template_id, "alpha", field_label="Alpha Label")
    beta = _make_field(template_id, "beta")
    _make_field(template_id, "gamma")  # absent from payload -> deleted

    response = client.put(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={
            "fields": [
                # Update: client display_order ignored (array index wins).
                {
                    "id": beta,
                    "field_name": "beta",
                    "field_label": "Beta Edited",
                    "display_order": 99,
                },
                # Create: defaults filled, source -> manual.
                {
                    "field_name": "delta",
                    "field_type": "number",
                    "is_required": False,
                },
                # Update + rename.
                {"id": alpha, "field_name": "alpha_renamed"},
            ]
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [f["field_name"] for f in body] == ["beta", "delta", "alpha_renamed"]
    assert [f["display_order"] for f in body] == [0, 1, 2]
    assert body[0]["field_label"] == "Beta Edited"
    assert body[0]["is_required"] is True  # not sent -> kept
    assert body[1]["field_type"] == "number"
    assert body[1]["is_required"] is False
    assert body[1]["source"] == "manual"
    assert body[2]["field_label"] == "Alpha Label"  # rename kept the label

    # Full-sync: gamma (absent) is gone; the ordered GET agrees.
    fields = _api_fields(owner_token, template_id)
    assert [f["field_name"] for f in fields] == ["beta", "delta", "alpha_renamed"]

    # Status advanced to field_configured.
    assert _db_status(template_id) == "field_configured"


def test_sync_422_duplicate_name_in_payload(owner_token):
    template_id = _make_template("API Sync Duplicate")
    existing = _make_field(template_id, "alpha")

    response = client.put(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={
            "fields": [
                {"id": existing, "field_name": "dupe"},
                {"field_name": "dupe"},
            ]
        },
    )
    assert response.status_code == 422
    # All-or-nothing: nothing was written.
    fields = _api_fields(owner_token, template_id)
    assert [f["field_name"] for f in fields] == ["alpha"]


def test_sync_422_foreign_id(owner_token):
    home = _make_template("API Sync Home")
    other = _make_template("API Sync Foreign")
    home_field = _make_field(home, "home_key")
    foreign_field = _make_field(other, "foreign_key")

    response = client.put(
        f"/api/v1/templates/{home}/fields",
        headers=_auth(owner_token),
        json={
            "fields": [
                {"id": home_field, "field_name": "home_key"},
                {"id": foreign_field, "field_name": "foreign_key"},
            ]
        },
    )
    assert response.status_code == 422
    # Both templates untouched.
    assert [f["field_name"] for f in _api_fields(owner_token, home)] == ["home_key"]
    assert [f["field_name"] for f in _api_fields(owner_token, other)] == ["foreign_key"]


def test_sync_409_name_swap_rolls_back(owner_token):
    template_id = _make_template("API Sync Swap")
    x = _make_field(template_id, "x")
    y = _make_field(template_id, "y")

    # Renaming x -> y collides with y (kept, renamed to z in the same save).
    response = client.put(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={
            "fields": [
                {"id": x, "field_name": "y"},
                {"id": y, "field_name": "z"},
            ]
        },
    )
    assert response.status_code == 409
    # All-or-nothing: original state preserved.
    fields = _api_fields(owner_token, template_id)
    assert [f["field_name"] for f in fields] == ["x", "y"]
    assert [f["display_order"] for f in fields] == [0, 1]


def test_sync_empty_payload_clears_without_status_advance(owner_token):
    template_id = _make_template("API Sync Clear")
    _make_field(template_id, "alpha")
    _make_field(template_id, "beta")

    response = client.put(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={"fields": []},
    )
    assert response.status_code == 200
    assert response.json() == []
    assert _api_fields(owner_token, template_id) == []
    # No fields -> mark_configured does not advance.
    assert _db_status(template_id) == "placeholder_detected"


def test_sync_mark_configured_false_keeps_status(owner_token):
    template_id = _make_template("API Sync No Advance")

    response = client.put(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={"fields": [{"field_name": "solo"}], "mark_configured": False},
    )
    assert response.status_code == 200
    assert _db_status(template_id) == "placeholder_detected"


def test_sync_forward_only_never_downgrades_active(owner_token):
    template_id = _make_template("API Sync Active", status="active")

    response = client.put(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={"fields": [{"field_name": "solo"}]},
    )
    assert response.status_code == 200
    assert _db_status(template_id) == "active"


def test_sync_403_for_stranger(stranger_token, owner_token):
    template_id = _make_template("API Sync Not Owner")
    _make_field(template_id, "alpha")

    response = client.put(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(stranger_token),
        json={"fields": [{"field_name": "hijacked"}]},
    )
    assert response.status_code == 403
    fields = _api_fields(owner_token, template_id)
    assert [f["field_name"] for f in fields] == ["alpha"]


# ── Locked templates reject every field write ─────────────────────


def test_locked_template_rejects_all_field_writes(owner_token):
    template_id = _make_template("API Locked", status="locked")
    field_id = _make_field(template_id, "alpha")

    create = client.post(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={"field_name": "new_field"},
    )
    assert create.status_code == 403
    assert "locked" in create.json()["detail"].lower()

    update = client.patch(
        f"/api/v1/templates/{template_id}/fields/{field_id}",
        headers=_auth(owner_token),
        json={"field_label": "nope"},
    )
    assert update.status_code == 403

    delete = client.delete(
        f"/api/v1/templates/{template_id}/fields/{field_id}",
        headers=_auth(owner_token),
    )
    assert delete.status_code == 403

    reorder = client.put(
        f"/api/v1/templates/{template_id}/fields/reorder",
        headers=_auth(owner_token),
        json={"ordered_ids": [field_id]},
    )
    assert reorder.status_code == 403

    sync = client.put(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(owner_token),
        json={"fields": [{"field_name": "hijacked"}]},
    )
    assert sync.status_code == 403

    # The locked template's fields are untouched.
    fields = _api_fields(owner_token, template_id)
    assert [f["field_name"] for f in fields] == ["alpha"]


# ── Reads stay viewer-accessible while writes are owner-only ──────


def test_stranger_reads_public_fields_but_cannot_write(stranger_token, owner_token):
    template_id = _make_template("API Public Read", visibility="public")
    _make_field(template_id, "alpha")

    read = client.get(
        f"/api/v1/templates/{template_id}/fields",
        headers=_auth(stranger_token),
    )
    assert read.status_code == 200
    assert [f["field_name"] for f in read.json()] == ["alpha"]

    write = client.patch(
        f"/api/v1/templates/{template_id}/fields/{read.json()[0]['id']}",
        headers=_auth(stranger_token),
        json={"field_label": "hijacked"},
    )
    assert write.status_code == 403
