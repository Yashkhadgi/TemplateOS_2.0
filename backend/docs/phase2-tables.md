# V1.4 Phase 2 Tables

## Overview

Phase 2 of V1.4 (Smart Form Generator - Save Draft) requires two new tables to persist user-entered form values as document drafts.

## Table: `documents`

Stores document drafts created from templates.

### Schema

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | SERIAL | PRIMARY KEY | Auto-increment |
| `template_id` | INTEGER | NOT NULL, FK templates(id) ON DELETE CASCADE | The template this document is based on |
| `created_by` | INTEGER | NOT NULL, FK users(id) ON DELETE CASCADE | The user who created the document |
| `name` | VARCHAR(255) | NULL | Optional user-given name; auto-generated if null |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'draft' | draft, generated, submitted, approved, rejected, final |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Auto-update on modification |

### Indexes

- `ix_documents_template_id (template_id)`
- `ix_documents_created_by (created_by)`
- `ix_documents_status (status)`

### Relationships

- `template`: Many-to-One with `templates` (ON DELETE CASCADE)
- `creator`: Many-to-One with `users` (ON DELETE CASCADE)
- `values`: One-to-Many with `document_values` (cascade delete-orphan)

---

## Table: `document_values`

Stores user-entered values for each field in a document.

### Schema

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | SERIAL | PRIMARY KEY | Auto-increment |
| `document_id` | INTEGER | NOT NULL, FK documents(id) ON DELETE CASCADE | The document this value belongs to |
| `field_name` | VARCHAR(100) | NOT NULL | Matches template_fields.field_name |
| `value` | TEXT | NOT NULL | JSON string for list fields, plain string for others |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Auto-update on modification |

### Constraints

- **Unique constraint:** `uq_document_value_key (document_id, field_name)`
  - Ensures one value per field per document

### Indexes

- `ix_document_values_document_id (document_id)`

### Relationships

- `document`: Many-to-One with `documents` (ON DELETE CASCADE)

---

## Design Rationale

### Why `field_name` instead of `field_id`?

`document_values` uses `field_name` (string) as the join key rather than `field_id` (foreign key to `template_fields`) for **flexibility and stability**:

1. **Template reconfiguration**: If a template owner reconfigures fields (Phase 3), the `field_id` values may change or be deleted. Using `field_name` makes existing draft values more resilient.

2. **Denormalized by design**: The `field_name` is stable and meaningful. Documents should not break if the template's field configuration is edited after a draft is saved.

3. **No FK to `template_fields`**: This is intentional. The field metadata lives in `template_fields`, but the form values are stored against the string key.

### Why TEXT for `value`?

- Handles textareas (long text)
- Handles list fields as JSON arrays (e.g., `'["item1", "item2"]'`)
- Handles all primitive types as strings
- Simple to query and update

**Storage format by field type:**

| Field Type | Storage Example |
|---|---|
| `text` | `"Annual Fest Planning Meeting"` |
| `textarea` | `"Long multi-line\ntext content..."` |
| `date` | `"2026-09-13"` (ISO format) |
| `number` | `"25"` (string representation) |
| `list` | `'["Budget approval","Venue selection","Marketing plan"]'` (JSON string) |
| `signature` | `"signatures/user_123_sig.png"` (file path, V1.10) |

### Cascade Behavior

- **`documents.template_id → templates.id`**: ON DELETE CASCADE
  - If a template is deleted, all documents based on it are deleted

- **`documents.created_by → users.id`**: ON DELETE CASCADE
  - If a user is deleted, all their documents are deleted

- **`document_values.document_id → documents.id`**: ON DELETE CASCADE
  - If a document is deleted, all its values are deleted (enforced at DB level)
  - SQLAlchemy relationship also has `cascade="all, delete-orphan"`

### Document Status Values

Phase 2 introduces `status` for document lifecycle tracking:

| Status | Meaning | Set By |
|---|---|---|
| `draft` | User is still filling the form | Phase 2 (default on create) |
| `generated` | DOCX/PDF has been generated | V1.6 (after successful generation) |
| `submitted` | Sent for approval (optional) | V1.8 (approval flow) |
| `approved` | Approved by reviewer (optional) | V1.8 |
| `rejected` | Rejected by reviewer (optional) | V1.8 |
| `final` | Finalized, no further edits | V1.7 or V1.8 |

**Phase 2 only uses `draft`.** Other statuses are documented for forward compatibility.

---

## Migration Notes

### For Member 3 (Phase 2):

When creating the Alembic migration:

```python
# Use CURRENT_TIMESTAMP for cross-dialect compatibility (SQLite tests)
sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False)
sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False)

# Use sa.text() for all server_default values
sa.Column('status', sa.String(50), server_default=sa.text("'draft'"), nullable=False)
```

### SQLAlchemy Models:

**Document model** should include:
- Custom `__init__` for python-side defaults (status='draft')
- `@validates('status')` against `DOCUMENT_STATUSES` tuple
- Relationships to `Template`, `User`, and `DocumentValue`

**DocumentValue model** should include:
- `__table_args__` with the unique constraint
- Relationship to `Document`

---

## Phase 2 API Contract

These endpoints will be built by Member 2 in Phase 2:

- `POST /api/v1/documents/create` - Create document row
- `PUT /api/v1/documents/{id}/values` - Upsert values (validation enforced)
- `GET /api/v1/documents` - List user's drafts
- `GET /api/v1/documents/{id}` - Get document + values
- `GET /api/v1/documents/{id}/values` - Get values only

See the Phase 2 prompts for detailed specifications.

---

## Testing Checklist

When implementing Phase 2:

- [ ] Alembic upgrade/downgrade runs clean
- [ ] documents table created with all constraints
- [ ] document_values table created with unique constraint
- [ ] ON DELETE CASCADE verified (delete document → values deleted)
- [ ] Upsert behavior tested (insert new, update existing)
- [ ] Status validation enforced
- [ ] created_at/updated_at auto-populate correctly

---

## Summary

This design provides:
- ✅ Simple, flexible draft storage
- ✅ Resilient to template reconfiguration
- ✅ Clean cascade deletion
- ✅ Ready for V1.6 (generation), V1.7 (preview), V1.8 (approval)
- ✅ Cross-dialect compatible (SQLite tests + Neon production)
