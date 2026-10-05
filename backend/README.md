# Backend Foundation

## Run locally

1. Copy `.env.example` to `.env` in the repository root.
2. Set a valid `DATABASE_URL` for Neon PostgreSQL.
3. Use `backend/alembic.ini` as provided, or recreate it from `backend/alembic.ini.example`.
4. Alembic reads the database URL from the repository root `.env` through `backend/alembic/env.py`.
5. Install backend dependencies from `backend/requirements.txt`.
6. Run the API:

```bash
uvicorn app.main:app --reload
```

Run the command from the `backend/` directory.

## Authentication setup

Apply migrations before starting the API:

```bash
alembic upgrade head
```

Public signups always receive the `normal_user` role. To create a local test or
administrator account, run this from `backend/` after migrating:

```bash
python scripts/seed_user.py --email admin@example.com --password "change-this-password" --full-name "TemplateOS Admin" --role super_admin
```


Install development dependencies and run the isolated auth tests with:

```bash
pip install -r requirements-dev.txt
pytest -q
```
Set a long, random `JWT_SECRET_KEY` in the repository root `.env` outside local
throwaway development.


## Development/demo profiles

The repository root `.env.example` declares seven temporary development users,
one for each supported role. Copy those `SIT_*_EMAIL` and `SIT_*_PASSWORD`
variables into your local `.env`, apply migrations, and seed their profile data
from the `backend/` directory:

```bash
python scripts/seed_demo_users.py
```

The command is explicit (it is never run during application startup), reads
credentials at runtime, hashes passwords with the normal authentication helper,
and can be re-run without creating duplicate users. These accounts are for local
development only and must not be seeded in production.


### Persisted profile contract

Member 2 can expose these User attributes directly through the protected profile
schema: id, email, full_name, and role remain required; department,
organization, job_title, phone, avatar_url, signature_path, and preferences are
nullable. Demo preferences use the keys default_document_format (set to docx)
and email_notifications (set to false).
