#!/usr/bin/env python3
"""
V1.4 Phase 1 - Template Fields Data Verification

Verifies existing template_fields data in the database:
- Checks for valid field_type values (MVP set)
- Checks for display_order gaps or duplicates
- Checks for null/empty required fields
- Reports any malformed rows

Run from backend/:
    python scripts/verify_template_fields.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.template import Template
from app.models.template_field import TemplateField, FIELD_TYPES


def verify_template_fields():
    """Verify all template_fields data in the database."""
    db = SessionLocal()

    try:
        print("[INFO] Starting template_fields data verification...")
        print(f"[INFO] Expected field types: {FIELD_TYPES}")
        print()

        # Get all templates with fields
        templates = db.query(Template).filter(
            Template.status.in_(["field_configured", "field_mapping"])
        ).all()

        if not templates:
            print("[WARN] No templates found with status=field_configured or field_mapping")
            return

        print(f"[INFO] Found {len(templates)} template(s) to verify")
        print()

        total_issues = 0

        for template in templates:
            print(f"[CHECK] Template: {template.name} (id={template.id})")

            # Get all fields for this template
            fields = db.query(TemplateField).filter(
                TemplateField.template_id == template.id
            ).order_by(TemplateField.display_order).all()

            if not fields:
                print(f"  [WARN] No fields found for template {template.id}")
                total_issues += 1
                continue

            print(f"  [INFO] Found {len(fields)} field(s)")

            # Check 1: Valid field_type
            invalid_types = []
            for field in fields:
                if field.field_type not in FIELD_TYPES:
                    invalid_types.append(f"{field.field_name}: '{field.field_type}'")
                    total_issues += 1

            if invalid_types:
                print(f"  [ERROR] Invalid field types:")
                for inv in invalid_types:
                    print(f"    - {inv}")
            else:
                print(f"  [OK] All field types are valid")

            # Check 2: Display order (check for gaps, duplicates)
            display_orders = [f.display_order for f in fields]
            expected_orders = list(range(len(fields)))

            if display_orders != expected_orders:
                print(f"  [WARN] Display order issues:")
                print(f"    Expected: {expected_orders}")
                print(f"    Actual:   {display_orders}")

                # Check for duplicates
                duplicates = [order for order in set(display_orders) if display_orders.count(order) > 1]
                if duplicates:
                    print(f"    Duplicates: {duplicates}")
                    total_issues += 1

                # Check for gaps
                if max(display_orders) >= len(fields):
                    print(f"    Gaps detected (max order {max(display_orders)} for {len(fields)} fields)")
                    total_issues += 1
            else:
                print(f"  [OK] Display order is contiguous (0 to {len(fields)-1})")

            # Check 3: Required fields are not null
            null_field_names = []
            null_field_types = []
            null_display_orders = []

            for field in fields:
                issues = []
                if not field.field_name:
                    null_field_names.append(field.id)
                if not field.field_type:
                    null_field_types.append(field.id)
                if field.display_order is None:
                    null_display_orders.append(field.id)

            if null_field_names:
                print(f"  [ERROR] Fields with null field_name: {null_field_names}")
                total_issues += len(null_field_names)

            if null_field_types:
                print(f"  [ERROR] Fields with null field_type: {null_field_types}")
                total_issues += len(null_field_types)

            if null_display_orders:
                print(f"  [ERROR] Fields with null display_order: {null_display_orders}")
                total_issues += len(null_display_orders)

            if not (null_field_names or null_field_types or null_display_orders):
                print(f"  [OK] All required fields have values")

            # Check 4: Section grouping (informational, not an error)
            sections = {}
            for field in fields:
                sec = field.section or "(no section)"
                if sec not in sections:
                    sections[sec] = []
                sections[sec].append(field.field_name)

            print(f"  [INFO] Sections: {list(sections.keys())}")

            print()

        # Summary
        print("=" * 60)
        if total_issues == 0:
            print("[SUCCESS] All template_fields data verified successfully!")
            print("[SUCCESS] No malformed rows found.")
        else:
            print(f"[WARN] Found {total_issues} issue(s) in template_fields data")
            print("[INFO] Review errors above and fix via SQL or backend script")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    verify_template_fields()
