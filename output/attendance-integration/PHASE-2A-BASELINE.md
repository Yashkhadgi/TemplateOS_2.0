# Phase 2A: Backend Baseline

Date: 2026-10-05 (Asia/Kolkata)
Result: complete. All 209 existing backend tests pass after a test-only correction.

## Environment

Used the existing `backend/.venv` Python 3.12 environment. Installed the declared development requirements with:

```sh
.venv/bin/python -m pip install -r requirements-dev.txt --disable-pip-version-check
```

Application dependencies were already installed. Added `pytest==8.3.4`, `httpx==0.27.2`, and their missing dependencies (`httpcore`, `iniconfig`, `packaging`, `pluggy`). No requirements manifests or application dependencies were changed. The initial sandbox download failed to resolve PyPI; the approved network-enabled retry succeeded.

`.venv/bin/python -m pip check` passed: no broken requirements found.

## Test Results

| Run | Result | Evidence |
| --- | --- | --- |
| Initial unchanged suite | 208 passed, 1 failed, 63 warnings | `backend-baseline.xml` |
| After test correction | 209 passed, 0 failed, 63 warnings; 6.39 seconds | `backend-baseline-verified.xml` |

Both report files are in this directory. Tests covered the existing auth, profiles, templates, fields, cleaning, document persistence, storage, AI audit records, mocked AI suggestions, and included SQLite migration checks.

The test run explicitly selected `backend/tests`, excluding operational scripts such as `backend/scripts/test_db_connection.py`. It used SQLite, a test-only JWT secret, and separate temporary storage. Migration tests used their own temporary SQLite files. No migrations were applied to the configured PostgreSQL database. AI endpoint tests mock the provider; no live AI verification was performed.

Command used from `backend/` for the passing run:

```sh
env DATABASE_URL=sqlite:// \
  JWT_SECRET_KEY=<test-secret> \
  API_V1_PREFIX=/api/v1 \
  STORAGE_BASE_PATH=/private/tmp/templateos-baseline.qh0lCQ \
  .venv/bin/python -m pytest tests -q --tb=short \
  --junitxml=../output/attendance-integration/backend-baseline-verified.xml
```

For future runs, create a fresh directory with `mktemp -d /private/tmp/templateos-baseline.XXXXXX` and substitute the returned path for `STORAGE_BASE_PATH`.

## Test-Only Correction

Changed `backend/tests/test_ai_generations.py`, in `test_ai_generations_migration_up_down_up`.

The test upgraded to `head`, downgraded by one revision, and asserted that `ai_generations` had been removed. That assumption became stale when document migration `9a8b7c6d5e4f` followed AI migration `e5f2a8c6d4b7`. A one-step downgrade now removes document tables, correctly leaving the AI table in place.

The test now downgrades explicitly to `b9e5d2c8a740`, the AI migration's parent, before checking removal and upgrading to `head` again. This matches the explicit-revision approach already used by the field-constraint migration test. The original schema, foreign-key behavior, table-removal, and re-upgrade assertions remain intact. Associated comments were updated.

No production code or migration file changed.

## Remaining Limits

- 63 existing deprecation warnings remain: the Starlette/AnyIO portal alias and uses of `datetime.utcnow()` in document code. These do not fail this baseline and were not changed during attendance preparation.
- SQLite test success does not establish PostgreSQL-specific migration behavior. Verify new attendance migrations on disposable PostgreSQL before accepting database implementation.
- This phase did not exercise browser workflows, live PostgreSQL, or external AI services. The frontend production build passed during Phase 1 and was not rerun for a Python test-only change.
- The repository requests `graphify update .` after code edits. It was attempted but the command is not installed/on PATH. No graph existed at discovery; graph refresh remains unavailable.

## Scope and Next Checkpoint

The pre-existing `package-lock.json` change and untracked user files were preserved. Only one existing test file was edited; the local discovery documents and test reports were updated. Nothing was committed or pushed to GitHub.

Next: Phase 2B, define the attendance role/scope rules and student-account linking contract, followed by Phase 2C's schema, API, and screen contracts. No attendance application implementation has started.
