# backend/tests/test_form_rendering_data.py
"""
V1.4 Phase 1 - Form Rendering Data Contract Tests

Tests verify template_fields data structure is ready for dynamic form rendering:
- Part 1: Database-level tests (model structure, ordering, grouping)
- Part 2: API-level integration tests (GET /templates/{id}/fields endpoint)
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-v14-phase1")

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.template import Template
from app.models.template_field import TemplateField, FIELD_TYPES
from app.core.security import hash_password

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_field_types_are_mvp_set():
    """Test that FIELD_TYPES matches the MVP set."""
    mvp_types = {"text", "textarea", "date", "number", "list", "signature"}
    assert set(FIELD_TYPES) == mvp_types

def test_template_field_model_has_all_metadata(db):
    """Test that TemplateField model has all required metadata columns."""
    # Create a user
    user = User(email="test@example.com", full_name="Test User", hashed_password="hash")
    db.add(user)
    db.flush()

    # Create a template
    template = Template(
        name="Test Template",
        category="mom",
        visibility="public",
        status="field_configured",
        uploaded_by=user.id,
        original_filename="test.docx",
        original_file_path="templates/original/test.docx"
    )
    db.add(template)
    db.flush()

    # Create a field with all metadata
    field = TemplateField(
        template_id=template.id,
        field_name="test_field",
        field_label="Test Field",
        field_type="text",
        is_required=True,
        description="Test description",
        example_value="Example",
        validation_rule="email",
        section="Test Section",
        ai_enabled=True,
        display_order=0
    )
    db.add(field)
    db.commit()

    # Verify all attributes exist
    retrieved = db.query(TemplateField).filter_by(field_name="test_field").first()
    assert retrieved is not None
    assert retrieved.field_name == "test_field"
    assert retrieved.field_label == "Test Field"
    assert retrieved.field_type == "text"
    assert retrieved.is_required is True
    assert retrieved.description == "Test description"
    assert retrieved.example_value == "Example"
    assert retrieved.validation_rule == "email"
    assert retrieved.section == "Test Section"
    assert retrieved.ai_enabled is True
    assert retrieved.display_order == 0

def test_fields_ordered_by_display_order(db):
    """Test that fields can be ordered by display_order."""
    user = User(email="test@example.com", full_name="Test", hashed_password="hash")
    db.add(user)
    db.flush()

    template = Template(
        name="Test", category="mom", visibility="public",
        status="field_configured", uploaded_by=user.id,
        original_filename="test.docx", original_file_path="test.docx"
    )
    db.add(template)
    db.flush()

    # Create fields in random order
    fields_data = [
        {"field_name": "field_2", "display_order": 2},
        {"field_name": "field_0", "display_order": 0},
        {"field_name": "field_1", "display_order": 1},
    ]

    for fd in fields_data:
        field = TemplateField(
            template_id=template.id,
            field_name=fd["field_name"],
            field_type="text",
            display_order=fd["display_order"]
        )
        db.add(field)
    db.commit()

    # Query ordered by display_order
    ordered_fields = db.query(TemplateField).filter_by(
        template_id=template.id
    ).order_by(TemplateField.display_order).all()

    assert len(ordered_fields) == 3
    assert ordered_fields[0].field_name == "field_0"
    assert ordered_fields[1].field_name == "field_1"
    assert ordered_fields[2].field_name == "field_2"

def test_fields_can_be_grouped_by_section(db):
    """Test that fields with sections can be grouped."""
    user = User(email="test@example.com", full_name="Test", hashed_password="hash")
    db.add(user)
    db.flush()

    template = Template(
        name="Test", category="mom", visibility="public",
        status="field_configured", uploaded_by=user.id,
        original_filename="test.docx", original_file_path="test.docx"
    )
    db.add(template)
    db.flush()

    # Create fields with different sections
    fields = [
        TemplateField(template_id=template.id, field_name="title", section="Details", display_order=0, field_type="text"),
        TemplateField(template_id=template.id, field_name="date", section="Details", display_order=1, field_type="date"),
        TemplateField(template_id=template.id, field_name="summary", section="Content", display_order=2, field_type="textarea"),
        TemplateField(template_id=template.id, field_name="notes", section=None, display_order=3, field_type="text"),
    ]
    for f in fields:
        db.add(f)
    db.commit()

    # Group by section
    all_fields = db.query(TemplateField).filter_by(template_id=template.id).order_by(TemplateField.display_order).all()
    sections = {}
    for field in all_fields:
        sec = field.section or "General"
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(field)

    assert "Details" in sections
    assert "Content" in sections
    assert "General" in sections
    assert len(sections["Details"]) == 2
    assert len(sections["Content"]) == 1
    assert len(sections["General"]) == 1

def test_validation_rule_persists(db):
    """Test that validation_rule is stored and retrieved."""
    user = User(email="test@example.com", full_name="Test", hashed_password="hash")
    db.add(user)
    db.flush()

    template = Template(
        name="Test", category="mom", visibility="public",
        status="field_configured", uploaded_by=user.id,
        original_filename="test.docx", original_file_path="test.docx"
    )
    db.add(template)
    db.flush()

    field = TemplateField(
        template_id=template.id,
        field_name="email",
        field_type="text",
        validation_rule="email",
        display_order=0
    )
    db.add(field)
    db.commit()

    retrieved = db.query(TemplateField).filter_by(field_name="email").first()
    assert retrieved.validation_rule == "email"


# ============================================================
# Part 2: API-Level Integration Tests
# ============================================================

@pytest.fixture
def client_with_db(db):
    """Create TestClient with database override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_token(db, client_with_db):
    """Create a user and return auth token."""
    # Create user
    user = User(
        email="testuser@example.com",
        full_name="Test User",
        hashed_password=hash_password("testpass123"),
        role="super_admin"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Login to get token
    response = client_with_db.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "testpass123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_api_get_fields_returns_ordered_list(db, client_with_db, auth_token):
    """Test GET /templates/{id}/fields returns ordered fields."""
    # Create user
    user = db.query(User).filter_by(email="testuser@example.com").first()

    # Create template
    template = Template(
        name="API Test Template",
        category="mom",
        visibility="public",
        status="field_configured",
        uploaded_by=user.id,
        original_filename="test.docx",
        original_file_path="test.docx"
    )
    db.add(template)
    db.flush()

    # Create fields in random order
    fields_data = [
        {"field_name": "field_b", "display_order": 2, "field_type": "text"},
        {"field_name": "field_a", "display_order": 0, "field_type": "text"},
        {"field_name": "field_c", "display_order": 1, "field_type": "date"},
    ]

    for fd in fields_data:
        field = TemplateField(template_id=template.id, **fd)
        db.add(field)
    db.commit()

    # Call API
    response = client_with_db.get(
        f"/api/v1/templates/{template.id}/fields",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    fields = response.json()

    # Assert ordered by display_order
    assert len(fields) == 3
    assert fields[0]["field_name"] == "field_a"
    assert fields[0]["display_order"] == 0
    assert fields[1]["field_name"] == "field_c"
    assert fields[1]["display_order"] == 1
    assert fields[2]["field_name"] == "field_b"
    assert fields[2]["display_order"] == 2


def test_api_get_fields_includes_all_metadata(db, client_with_db, auth_token):
    """Test GET /templates/{id}/fields includes all required metadata."""
    user = db.query(User).filter_by(email="testuser@example.com").first()

    template = Template(
        name="Metadata Test", category="mom", visibility="public",
        status="field_configured", uploaded_by=user.id,
        original_filename="test.docx", original_file_path="test.docx"
    )
    db.add(template)
    db.flush()

    # Create field with all metadata
    field = TemplateField(
        template_id=template.id,
        field_name="test_field",
        field_label="Test Field Label",
        field_type="textarea",
        is_required=True,
        description="This is a test description",
        example_value="Example text here",
        validation_rule="min:10",
        section="Test Section",
        ai_enabled=True,
        display_order=0
    )
    db.add(field)
    db.commit()

    # Call API
    response = client_with_db.get(
        f"/api/v1/templates/{template.id}/fields",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    fields = response.json()
    assert len(fields) == 1

    field_data = fields[0]
    # Check all MVP metadata is present
    assert field_data["field_name"] == "test_field"
    assert field_data["field_label"] == "Test Field Label"
    assert field_data["field_type"] == "textarea"
    assert field_data["field_type"] in FIELD_TYPES
    assert field_data["is_required"] is True
    assert field_data["description"] == "This is a test description"
    assert field_data["example_value"] == "Example text here"
    assert field_data["validation_rule"] == "min:10"
    assert field_data["section"] == "Test Section"
    assert field_data["ai_enabled"] is True
    assert field_data["display_order"] == 0
    # Check response includes id and timestamps
    assert "id" in field_data
    assert "template_id" in field_data
    assert "created_at" in field_data
    assert "updated_at" in field_data


def test_api_get_fields_supports_section_grouping(db, client_with_db, auth_token):
    """Test GET /templates/{id}/fields supports section grouping."""
    user = db.query(User).filter_by(email="testuser@example.com").first()

    template = Template(
        name="Section Test", category="mom", visibility="public",
        status="field_configured", uploaded_by=user.id,
        original_filename="test.docx", original_file_path="test.docx"
    )
    db.add(template)
    db.flush()

    # Create fields across 3 sections
    fields = [
        TemplateField(template_id=template.id, field_name="title", section="Header", display_order=0, field_type="text"),
        TemplateField(template_id=template.id, field_name="date", section="Header", display_order=1, field_type="date"),
        TemplateField(template_id=template.id, field_name="body", section="Content", display_order=2, field_type="textarea"),
        TemplateField(template_id=template.id, field_name="notes", section=None, display_order=3, field_type="text"),
    ]
    for f in fields:
        db.add(f)
    db.commit()

    # Call API
    response = client_with_db.get(
        f"/api/v1/templates/{template.id}/fields",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    fields = response.json()
    assert len(fields) == 4

    # Group by section (as Member 1 would in UI)
    sections = {}
    for field in fields:
        sec = field["section"] or "General"
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(field)

    assert "Header" in sections
    assert "Content" in sections
    assert "General" in sections
    assert len(sections["Header"]) == 2
    assert len(sections["Content"]) == 1
    assert len(sections["General"]) == 1

    # Verify ordering within sections
    assert sections["Header"][0]["field_name"] == "title"
    assert sections["Header"][1]["field_name"] == "date"


def test_api_get_fields_handles_null_sections(db, client_with_db, auth_token):
    """Test GET /templates/{id}/fields handles fields with section=null."""
    user = db.query(User).filter_by(email="testuser@example.com").first()

    template = Template(
        name="Null Section Test", category="notice", visibility="public",
        status="field_configured", uploaded_by=user.id,
        original_filename="test.docx", original_file_path="test.docx"
    )
    db.add(template)
    db.flush()

    # Create fields with null sections
    fields = [
        TemplateField(template_id=template.id, field_name="field1", section=None, display_order=0, field_type="text"),
        TemplateField(template_id=template.id, field_name="field2", section=None, display_order=1, field_type="text"),
    ]
    for f in fields:
        db.add(f)
    db.commit()

    # Call API
    response = client_with_db.get(
        f"/api/v1/templates/{template.id}/fields",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    fields = response.json()
    assert len(fields) == 2

    # All fields should be accessible even with null sections
    assert fields[0]["section"] is None
    assert fields[1]["section"] is None
    assert fields[0]["field_name"] == "field1"
    assert fields[1]["field_name"] == "field2"
