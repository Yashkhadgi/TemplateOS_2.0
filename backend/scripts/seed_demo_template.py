#!/usr/bin/env python3
"""
V1.4 Phase 1 - Demo Template Seeder

Seeds a demo template with 3 sections, 8 fields, and varied types
for Member 1 to test the dynamic form rendering UI.

Run from backend/:
    python scripts/seed_demo_template.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.user import User
from app.models.template import Template
from app.models.template_field import TemplateField


def seed_demo_template():
    """Seed a demo template for V1.4 Phase 1 testing."""
    db = SessionLocal()
    try:
        # Find a user to own the template (use the first super_admin or create one)
        owner = db.query(User).filter(User.role == "super_admin").first()
        if not owner:
            # Try any user
            owner = db.query(User).first()

        if not owner:
            print("[ERROR] No users found in database.")
            print("[INFO] Create a user first via signup or seed_demo_users.py")
            return

        # Check if demo template already exists
        existing = db.query(Template).filter(Template.name == "Meeting Minutes Demo").first()
        if existing:
            print(f"[INFO] Demo template already exists (id={existing.id})")
            print(f"[INFO] Delete it first if you want to recreate")
            return

        # Create template
        template = Template(
            name="Meeting Minutes Demo",
            description="A demo template with varied field types for V1.4 testing",
            category="mom",
            visibility="public",
            status="field_configured",
            uploaded_by=owner.id,
            original_filename="demo.docx",
            original_file_path="templates/original/demo.docx"  # stub for Phase 1
        )
        db.add(template)
        db.flush()

        # Add fields (3 sections, varied types)
        fields = [
            # Section: Meeting Details
            {
                "field_name": "meeting_title",
                "field_label": "Meeting Title",
                "field_type": "text",
                "is_required": True,
                "section": "Meeting Details",
                "display_order": 0,
                "description": "Enter the official meeting title",
                "example_value": "Annual Fest Planning Meeting",
                "ai_enabled": False
            },
            {
                "field_name": "meeting_date",
                "field_label": "Meeting Date",
                "field_type": "date",
                "is_required": True,
                "section": "Meeting Details",
                "display_order": 1,
                "description": "Select the meeting date",
                "example_value": "2026-09-13",
                "ai_enabled": False
            },
            {
                "field_name": "department",
                "field_label": "Department",
                "field_type": "text",
                "is_required": False,
                "section": "Meeting Details",
                "display_order": 2,
                "description": "Department conducting the meeting",
                "example_value": "Computer Science",
                "ai_enabled": False
            },

            # Section: Agenda
            {
                "field_name": "agenda_items",
                "field_label": "Agenda Items",
                "field_type": "list",
                "is_required": True,
                "section": "Agenda",
                "display_order": 3,
                "description": "List the main topics to discuss",
                "example_value": '["Budget approval", "Venue selection"]',
                "ai_enabled": False
            },
            {
                "field_name": "discussion_points",
                "field_label": "Discussion Points",
                "field_type": "textarea",
                "is_required": False,
                "section": "Agenda",
                "display_order": 4,
                "description": "Detailed discussion notes",
                "example_value": "Key points discussed during the meeting",
                "ai_enabled": True
            },

            # Section: Outcome
            {
                "field_name": "outcome_summary",
                "field_label": "Outcome Summary",
                "field_type": "textarea",
                "is_required": True,
                "section": "Outcome",
                "display_order": 5,
                "description": "Summarize the meeting outcomes and decisions",
                "example_value": "Decisions made and next steps agreed upon",
                "ai_enabled": True
            },
            {
                "field_name": "action_items",
                "field_label": "Action Items",
                "field_type": "list",
                "is_required": False,
                "section": "Outcome",
                "display_order": 6,
                "description": "Action items assigned during the meeting",
                "example_value": '["Follow up with vendors", "Book venue by Friday"]',
                "ai_enabled": False
            },
            {
                "field_name": "prepared_by_email",
                "field_label": "Prepared By (Email)",
                "field_type": "text",
                "is_required": True,
                "section": "Outcome",
                "display_order": 7,
                "description": "Email of the person preparing these minutes",
                "example_value": "john@example.com",
                "validation_rule": "email",
                "ai_enabled": False
            },
        ]

        for f in fields:
            field = TemplateField(template_id=template.id, **f)
            db.add(field)

        db.commit()

        print(f"[OK] Demo template created successfully!")
        print(f"[OK] Template ID: {template.id}")
        print(f"[OK] Template name: {template.name}")
        print(f"[OK] Owner: {owner.full_name} ({owner.email})")
        print(f"[OK] Fields added: 8 fields across 3 sections")
        print(f"")
        print(f"[INFO] This template is ready for V1.4 Phase 1 form rendering tests")

    except Exception as e:
        print(f"[ERROR] Failed to seed demo template: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_template()
