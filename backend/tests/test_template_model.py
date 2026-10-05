import pytest
from app.models.template import Template

def test_template_defaults():
    t = Template(
        name="Test",
        category="notice",
        visibility="private",
        uploaded_by=1,
        original_file_path="templates/original/abc.docx",
    )
    assert t.status == "uploaded"
    assert t.version == 1
    assert t.is_locked is False
    assert isinstance(t.original_file_path, str)
    assert b"" not in [t.original_file_path]  # ensure it's not bytes

def test_template_invalid_category_raises():
    with pytest.raises(ValueError):
        Template(name="Test", category="invalid_xyz", visibility="private", uploaded_by=1)

def test_template_invalid_visibility_raises():
    with pytest.raises(ValueError):
        Template(name="Test", category="notice", visibility="invalid_xyz", uploaded_by=1)

def test_template_invalid_status_raises():
    t = Template(name="Test", category="notice", visibility="private", uploaded_by=1)
    with pytest.raises(ValueError):
        t.status = "invalid_xyz"

def test_template_path_field_is_string_type():
    t = Template(name="Test", category="notice", visibility="private", uploaded_by=1, original_file_path="templates/original/test.docx")
    assert isinstance(t.original_file_path, str) is True

def test_template_version_default():
    t = Template(name="Test", category="notice", visibility="private", uploaded_by=1)
    assert t.version == 1
