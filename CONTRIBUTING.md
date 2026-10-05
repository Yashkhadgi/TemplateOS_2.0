# Contributing to TemplateOS

This repository uses a small, reviewable commit history. Keep each commit focused on one logical change and verify it before moving to the next step.

## Workflow

1. Start from the latest `main` branch.
2. Create a short-lived branch such as `feature/attendance-events` or `fix/document-validation`.
3. Keep frontend, backend, migration, and test changes together only when they implement one coherent behavior.
4. Run the relevant backend tests and frontend build.
5. Review the complete diff before committing or opening a pull request.

## Repository Rules

- Never commit `.env`, credentials, API keys, database URLs, local storage, archives, generated reports, build output, or virtual environments.
- Use `.env.example` only for variable names and safe local defaults.
- Keep migrations additive and test upgrade/downgrade behavior with disposable data.
- Enforce authorization in the backend. Frontend role checks are user-interface behavior only.
- Preserve existing template and document workflows when adding attendance features.
- Add tests in proportion to risk, especially for authentication, scope boundaries, state transitions, and migrations.

## Commits

Use clear messages such as:

- `chore: initialize TemplateOS workspace`
- `feat(backend): add JWT authentication foundation`
- `feat(frontend): add template library workflow`
- `docs: define attendance integration contract`

Avoid combining unrelated cleanup, feature work, and formatting in one commit.

## Pull Requests

Describe the behavior change, affected areas, verification performed, migration or environment impact, and known limitations. Use squash merge for focused feature branches unless the repository owner chooses another policy.
