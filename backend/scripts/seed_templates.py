"""
Seed sample templates for demo purposes.
Usage: python -m scripts.seed_templates (from backend/ directory)
"""
import random
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.template import Template


SAMPLE_TEMPLATES = [
    {
        "name": "Official Notice Format",
        "category": "notice",
        "visibility": "public",
        "status": "active",
        "description": "Standard official notice template for institutional announcements.",
    },
    {
        "name": "Faculty Meeting MoM",
        "category": "mom",
        "visibility": "public",
        "status": "active",
        "description": "Minutes of meeting template for faculty and committee meetings.",
    },
    {
        "name": "Annual Report Template",
        "category": "report",
        "visibility": "public",
        "status": "active",
        "description": "Comprehensive annual report template with sections for achievements and finances.",
    },
    {
        "name": "Leave Application Form",
        "category": "application",
        "visibility": "public",
        "status": "active",
        "description": "Standard leave application form for employees and students.",
    },
    {
        "name": "Formal Letter Template",
        "category": "letter",
        "visibility": "public",
        "status": "active",
        "description": "Professional formal letter template with proper formatting.",
    },
    {
        "name": "Achievement Certificate",
        "category": "certificate",
        "visibility": "public",
        "status": "active",
        "description": "Certificate of achievement template for awards and recognition.",
    },
    {
        "name": "Project Proposal Template",
        "category": "proposal",
        "visibility": "public",
        "status": "active",
        "description": "Detailed project proposal template with budget and timeline sections.",
    },
    {
        "name": "Department Invoice Format",
        "category": "invoice",
        "visibility": "public",
        "status": "active",
        "description": "Invoice template for departmental billing and procurement.",
    },
    {
        "name": "Custom Event Agenda",
        "category": "custom",
        "visibility": "public",
        "status": "active",
        "description": "Customizable event agenda template for seminars and workshops.",
    },
    {
        "name": "Personal Notes Template",
        "category": "custom",
        "visibility": "private",
        "status": "uploaded",
        "description": "Personal notes template for internal use.",
    },
    {
        "name": "Department-only Notice",
        "category": "notice",
        "visibility": "department",
        "status": "uploaded",
        "description": "Notice template restricted to department members.",
    },
    {
        "name": "Organization Circular Template",
        "category": "notice",
        "visibility": "organization",
        "status": "active",
        "description": "Circular template for organization-wide distribution.",
    },
]


def slugify(name: str) -> str:
    """Convert a template name to a slug for file paths."""
    return name.lower().replace(" ", "-").replace("'", "")


def main() -> None:
    created = 0
    skipped = 0

    with SessionLocal() as db:
        # Find the first user to assign templates to
        from app.models.user import User
        first_user = db.execute(select(User).order_by(User.id)).scalars().first()
        if first_user is None:
            print("ERROR: No users found in the database. Please create a user first.")
            print("  Run: python -m scripts.seed_demo_users")
            sys.exit(1)

        user_id = first_user.id
        print(f"Seeding templates for user: {first_user.email} (id={user_id})")

        for tmpl_data in SAMPLE_TEMPLATES:
            # Check if template already exists by name
            existing = db.execute(
                select(Template).where(Template.name == tmpl_data["name"])
            ).scalars().first()

            if existing is not None:
                skipped += 1
                continue

            slug = slugify(tmpl_data["name"])
            template = Template(
                name=tmpl_data["name"],
                description=tmpl_data["description"],
                category=tmpl_data["category"],
                visibility=tmpl_data["visibility"],
                status=tmpl_data["status"],
                original_file_path=f"templates/original/sample-{slug}.docx",
                original_filename=f"{tmpl_data['name']}.docx",
                file_size_bytes=random.randint(15000, 100000),
                file_extension=".docx",
                version=1,
                uploaded_by=user_id,
            )
            db.add(template)
            created += 1

        db.commit()

    print(f"Created {created} sample templates. Skipped {skipped} already existing.")


if __name__ == "__main__":
    main()
