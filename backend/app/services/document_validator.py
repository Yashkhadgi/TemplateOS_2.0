"""
Document validation service for V1.4 Phase 2.

Validates document_values against template_fields metadata:
- Required field checks
- Type validation (number, email)
- validation_rule enforcement (email, min:N, max:N)
"""

import re
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from app.models.template_field import TemplateField


# Regex for email validation
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _parse_validation_rule(rule: str) -> dict | None:
    """
    Parse validation_rule string into structured format.

    Supported formats:
    - "email"
    - "min:N" (N = integer)
    - "max:N" (N = integer)
    - "min:N|max:M" (combined)
    - "email|min:5" (combined with pipe)
    """
    if not rule:
        return None

    parts = rule.split("|")
    parsed = {}

    for part in parts:
        part = part.strip()
        if part == "email":
            parsed["email"] = True
        elif part.startswith("min:"):
            try:
                parsed["min"] = int(part.split(":")[1])
            except (IndexError, ValueError):
                pass
        elif part.startswith("max:"):
            try:
                parsed["max"] = int(part.split(":")[1])
            except (IndexError, ValueError):
                pass

    return parsed if parsed else None


def validate_document_values(
    fields: list["TemplateField"], values: list[dict]
) -> list[dict]:
    """
    Validate document values against template field definitions.

    Args:
        fields: List of TemplateField objects from the template
        values: List of dicts with {field_name, value}

    Returns:
        The validated values list (unchanged, for chaining)

    Raises:
        HTTPException(422): If any validation fails, detail contains list of
        {field_name, error} objects.
    """
    errors = []
    field_map = {f.field_name: f for f in fields}

    for value_dict in values:
        field_name = value_dict.get("field_name")
        value = value_dict.get("value", "")

        if not field_name:
            errors.append({"field_name": field_name, "error": "field_name is required"})
            continue

        field = field_map.get(field_name)
        if not field:
            errors.append(
                {"field_name": field_name, "error": "Field not found in template"}
            )
            continue

        # Required check
        if field.is_required and not value.strip():
            errors.append({"field_name": field_name, "error": "This field is required"})
            continue

        # Skip further validation if value is empty and not required
        if not value.strip() and not field.is_required:
            continue

        # Type validation: number
        if field.field_type == "number":
            try:
                float(value)
            except ValueError:
                errors.append(
                    {"field_name": field_name, "error": "Must be a valid number"}
                )
                continue

        # Validation rule parsing
        rule_parsed = _parse_validation_rule(field.validation_rule)
        if rule_parsed:
            # Email validation
            if rule_parsed.get("email"):
                if not EMAIL_REGEX.match(value):
                    errors.append(
                        {
                            "field_name": field_name,
                            "error": "Must be a valid email address",
                        }
                    )

            # Min validation
            if "min" in rule_parsed:
                min_val = rule_parsed["min"]
                if field.field_type == "number":
                    try:
                        if float(value) < min_val:
                            errors.append(
                                {
                                    "field_name": field_name,
                                    "error": f"Must be at least {min_val}",
                                }
                            )
                    except ValueError:
                        pass  # Already caught by number validation
                else:
                    if len(value) < min_val:
                        errors.append(
                            {
                                "field_name": field_name,
                                "error": f"Must be at least {min_val} characters",
                            }
                        )

            # Max validation
            if "max" in rule_parsed:
                max_val = rule_parsed["max"]
                if field.field_type == "number":
                    try:
                        if float(value) > max_val:
                            errors.append(
                                {
                                    "field_name": field_name,
                                    "error": f"Must be at most {max_val}",
                                }
                            )
                    except ValueError:
                        pass
                else:
                    if len(value) > max_val:
                        errors.append(
                            {
                                "field_name": field_name,
                                "error": f"Must be at most {max_val} characters",
                            }
                        )

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors,
        )

    return values
