# Validation Rules

## Overview

The `validation_rule` field on `template_fields` is a `VARCHAR(255)` nullable column that stores client-side and server-side validation rules for form fields. This document defines the format, parsing rules, and enforcement responsibilities for V1.4 (Smart Form Generator).

## Format

The `validation_rule` field supports these patterns:

| Pattern | Example | Meaning | Phase 1 (Client) | Phase 2 (Server) |
|---|---|---|---|---|
| `email` | `"email"` | Validates email format (RFC 5322) | ✅ Zod email() | ✅ Regex validation |
| `min:N` | `"min:5"` | Minimum length (string) or value (number) | ✅ Zod min() | ✅ Pydantic validation |
| `max:N` | `"max:100"` | Maximum length (string) or value (number) | ✅ Zod max() | ✅ Pydantic validation |
| `regex:<pattern>` | `"regex:^[A-Z]+$"` | Custom regex pattern | ❌ Ignored | ✅ re.match() validation |
| Multi-rule | `"min:5\|max:100"` | Multiple rules separated by `\|` | ✅ Chained Zod | ✅ All rules enforced |
| Empty/null | `null` or `""` | No extra validation | ✅ Type + required only | ✅ Type + required only |

**Note:** Use pipe character `|` as the delimiter for multiple rules (e.g., `"min:5|max:100"`).

## Phase 1 (Frontend - Dynamic Form Rendering)

**Responsibility:** Member 1 (Frontend Developer)

**Scope:** Client-side validation using Zod

### Supported Rules
- `email` → `z.string().email()`
- `min:N` → `z.string().min(N)` or `z.number().min(N)` (depends on field_type)
- `max:N` → `z.string().max(N)` or `z.number().max(N)` (depends on field_type)

### Ignored Rules
- `regex:<pattern>` — Backend-only, not parsed in Phase 1

### Parsing Logic
```typescript
// Example: Parse validation_rule string for Zod
function parseValidationRule(rule: string | null, fieldType: string) {
  if (!rule) return null;

  const rules = rule.split('|').map(r => r.trim());
  const parsed: any = {};

  for (const r of rules) {
    if (r === 'email') parsed.email = true;
    else if (r.startsWith('min:')) parsed.min = parseInt(r.split(':')[1]);
    else if (r.startsWith('max:')) parsed.max = parseInt(r.split(':')[1]);
    // regex is ignored (server-only)
  }

  return parsed;
}
```

### Example Zod Schema
```typescript
// For field: { field_type: "text", validation_rule: "email" }
z.string().email("Invalid email format")

// For field: { field_type: "text", validation_rule: "min:5|max:100" }
z.string().min(5, "Minimum 5 characters").max(100, "Maximum 100 characters")

// For field: { field_type: "number", validation_rule: "min:1|max:100" }
z.number().min(1, "Minimum value: 1").max(100, "Maximum value: 100")
```

## Phase 2 (Backend - Save Draft)

**Responsibility:** Member 2 (Backend Developer)

**Scope:** Server-side validation when saving `document_values`

### Enforcement
All rules are enforced server-side in the `PUT /documents/{id}/values` endpoint:
- `email` → Python regex validation (RFC 5322 simplified)
- `min:N` → `len(value) >= N` (string) or `float(value) >= N` (number)
- `max:N` → `len(value) <= N` (string) or `float(value) <= N` (number)
- `regex:<pattern>` → `re.match(pattern, value)`

### Validation Flow
```python
# Pseudocode for Phase 2 validation
def validate_field_value(field: TemplateField, value: str) -> None:
    """Validate a document_value against its field's validation_rule."""
    if not field.validation_rule:
        return  # No extra validation

    rules = field.validation_rule.split('|')

    for rule in rules:
        rule = rule.strip()

        if rule == 'email':
            if not is_valid_email(value):
                raise ValidationError(f"{field.field_label}: Invalid email format")

        elif rule.startswith('min:'):
            min_val = int(rule.split(':')[1])
            if field.field_type in ('text', 'textarea'):
                if len(value) < min_val:
                    raise ValidationError(f"{field.field_label}: Minimum {min_val} characters")
            elif field.field_type == 'number':
                if float(value) < min_val:
                    raise ValidationError(f"{field.field_label}: Minimum value {min_val}")

        elif rule.startswith('max:'):
            max_val = int(rule.split(':')[1])
            if field.field_type in ('text', 'textarea'):
                if len(value) > max_val:
                    raise ValidationError(f"{field.field_label}: Maximum {max_val} characters")
            elif field.field_type == 'number':
                if float(value) > max_val:
                    raise ValidationError(f"{field.field_label}: Maximum value {max_val}")

        elif rule.startswith('regex:'):
            pattern = rule[6:]  # Remove 'regex:' prefix
            if not re.match(pattern, value):
                raise ValidationError(f"{field.field_label}: Does not match required pattern")
```

### Error Response
When validation fails, return HTTP 422 with structured errors:
```json
{
  "detail": [
    {
      "field_name": "prepared_by_email",
      "field_label": "Prepared By (Email)",
      "message": "Invalid email format",
      "rule": "email"
    },
    {
      "field_name": "meeting_title",
      "field_label": "Meeting Title",
      "message": "Minimum 5 characters",
      "rule": "min:5"
    }
  ]
}
```

## Field Type Context

Validation rules behave differently based on `field_type`:

| field_type | min/max applies to | email | regex |
|---|---|---|---|
| `text` | String length | ✅ Allowed | ✅ Allowed |
| `textarea` | String length | ❌ N/A | ✅ Allowed |
| `number` | Numeric value | ❌ N/A | ✅ Allowed (as string) |
| `date` | N/A (ISO format enforced) | ❌ N/A | ✅ Allowed (date format) |
| `list` | Array length (Phase 2) | ❌ N/A | ❌ N/A |
| `signature` | N/A (V1.10 feature) | ❌ N/A | ❌ N/A |

## Examples from Demo Template

The `seed_demo_template.py` script includes these validation examples:

```python
# Email validation
{
    "field_name": "prepared_by_email",
    "field_type": "text",
    "validation_rule": "email",
    "example_value": "john@example.com"
}

# Length constraints
{
    "field_name": "meeting_title",
    "field_type": "text",
    "validation_rule": "min:5|max:100",
    "example_value": "Annual Fest Planning Meeting"
}

# Numeric range
{
    "field_name": "attendee_count",
    "field_type": "number",
    "validation_rule": "min:1|max:500",
    "example_value": "25"
}

# Custom regex (server-only)
{
    "field_name": "department_code",
    "field_type": "text",
    "validation_rule": "regex:^[A-Z]{2,4}$",
    "example_value": "CS"
}
```

## Testing Checklist

### Phase 1 (Frontend)
- [ ] Parse `email` rule and apply Zod `.email()`
- [ ] Parse `min:N` and apply Zod `.min(N)`
- [ ] Parse `max:N` and apply Zod `.max(N)`
- [ ] Parse multi-rule `"min:5|max:100"` and chain Zod validators
- [ ] Ignore `regex:<pattern>` rules (no client-side regex)
- [ ] Handle `null` or empty `validation_rule` gracefully

### Phase 2 (Backend)
- [ ] Enforce `email` rule server-side (reject invalid emails)
- [ ] Enforce `min:N` for text (string length) and number (numeric value)
- [ ] Enforce `max:N` for text (string length) and number (numeric value)
- [ ] Enforce `regex:<pattern>` rules (server-only)
- [ ] Enforce multi-rule `"min:5|max:100"` (all rules must pass)
- [ ] Return HTTP 422 with structured error details on validation failure

## Future Extensions

**V1.5+ may add:**
- `required_if:<field_name>` — Conditional required based on another field
- `date_after:<field_name>` — Date must be after another date field
- `date_before:<field_name>` — Date must be before another date field
- `url` — URL format validation
- `phone` — Phone number format validation (locale-aware)

These are not implemented in V1.4 Phase 1 or 2.

## References

- **Phase 1 Frontend Implementation:** See `frontend/src/components/DynamicForm/` (Member 1)
- **Phase 2 Backend Implementation:** See `backend/app/api/v1/endpoints/documents.py` (Member 2, Phase 2)
- **Template Field Model:** `backend/app/models/template_field.py` (V1.3)
- **Demo Data:** `backend/scripts/seed_demo_template.py` (Member 3, Phase 1)

## Summary

| Aspect | Phase 1 (Client) | Phase 2 (Server) |
|---|---|---|
| **Responsibility** | Member 1 (Frontend) | Member 2 (Backend) |
| **Technology** | Zod validation | Pydantic + custom validators |
| **Rules Supported** | email, min, max | email, min, max, regex |
| **Scope** | Form submission validation | API request validation |
| **Error Handling** | Inline form errors | HTTP 422 response |

**Key Principle:** Client-side validation improves UX, but server-side validation is the source of truth. All rules must be enforced server-side in Phase 2.
