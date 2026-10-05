# TemplateOS

TemplateOS is a React and FastAPI workspace for creating reusable document templates, detecting and configuring placeholders, generating document drafts, and managing role-aware workflows. Attendance and event management is being integrated as a bounded module using the same authentication, API, and PostgreSQL database.

## Stack

- React 18, TypeScript, Vite, Tailwind CSS
- FastAPI, SQLAlchemy, Alembic
- PostgreSQL in deployed environments; SQLite for isolated tests
- Optional AWS Bedrock field suggestions

## Local Setup

1. Copy `.env.example` to `.env` and provide a local `DATABASE_URL` and strong `JWT_SECRET_KEY`.
2. Install frontend dependencies from the repository root with `npm install`.
3. Create a Python virtual environment under `backend/.venv` and install `backend/requirements-dev.txt`.
4. Apply migrations from `backend/` with `alembic upgrade head`.

Run the backend from `backend/`:

```bash
uvicorn app.main:app --reload
```

Run the frontend from the repository root:

```bash
npm run dev:frontend
```

## Verification

```bash
cd backend
.venv/bin/python -m pytest tests -q
cd ..
npm run build:frontend
```

Attendance integration contracts are under `output/attendance-integration/`. Imported ZIP contents, Firebase configuration, local reports, test XML, credentials, and environment files are deliberately excluded from version control.
