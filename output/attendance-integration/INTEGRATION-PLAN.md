# TemplateOS Attendance Integration

Discovery date: 2026-10-05 (Asia/Kolkata)
Status: Phase 1 discovery and Phase 2A baseline are complete. Phase 2B permissions are drafted. Phase 2C was drafted by Antigravity and requires contract review before implementation. Attendance implementation has not started.

Phase 2A result: 209 backend tests pass after correcting one stale migration test. See [Phase 2A baseline](PHASE-2A-BASELINE.md) for environment changes, initial failure, correction, and verification limits.

Phase 2B result: permission contract defines role-to-capability mapping, organization/department scope boundaries, student-account linking design, access assignment/revocation rules, and 46 permission test scenarios. See [Phase 2B permissions](PHASE-2B-PERMISSIONS.md).

Phase 2C result: Antigravity drafted 10 relational tables, API endpoints, state machines, optimistic concurrency, and a frontend screen map. Review found unresolved product decisions and incomplete or inconsistent endpoint rules; see [Phase 2C contract](PHASE-2C-CONTRACT.md) before implementation.

## Working agreement

- Work locally only. Never push to GitHub, on any branch.
- Deliver one phase or small part at a time, with a reviewable result and verification.
- Keep TemplateOS's existing structure, login, template workflows, and document workflows.
- Add attendance as a bounded feature; do not replace the app or upgrade its framework stack for this integration.
- The user confirmed there are no existing Firebase users or data to preserve. Port features into TemplateOS; no Firebase migration is needed.
- Preserve pre-existing local changes, including `package-lock.json`, and untracked files.
- Aim for a cohesive, polished interface. Do not promise an issue-free integration; use explicit checks at each checkpoint.

## Phase 1: What Was Inspected

Extracted `TrackMyAttendance-main.zip` into `output/attendance-integration/TrackMyAttendance-main/` using non-overwriting extraction. The ZIP and extracted source remain reference material outside the application workspace package.

Inspected TemplateOS routing, layout, sidebar, auth context, API client, backend auth dependencies, user roles, template access rules, API registration, dependency manifests, test setup, and styling. Inspected the attendance app's entry point, navigation, portal workflows, types, Firebase initialization, supplied access rules, database service, import/export utilities, and build configuration. This is an architectural discovery pass, not a complete line-by-line audit or browser verification.

| Area | TemplateOS | Attendance ZIP | Integration decision |
| --- | --- | --- | --- |
| UI | React 18, TypeScript, React Router 6 | Declares React 19, TypeScript, local-state tabs | Keep the host stack and add routed attendance pages |
| Build | Vite 5 | Declares Vite 8 | Keep the host build system |
| Styling | Tailwind 3, Radix-based shared controls | Declares Tailwind 4 with newer utility names | Adapt attendance UI to existing tokens and controls |
| Login | FastAPI JWT, hashed passwords, persisted users | Browser credential checks and localStorage user objects | Reuse TemplateOS authentication |
| Data | SQLAlchemy, PostgreSQL, Alembic | Direct browser-to-Firestore operations | Add attendance models, services, and endpoints |
| Roles | Seven existing roles | STUDENT, ORGANISER, ADMIN | Define attendance permissions using existing roles |
| Reports | DOCX/template document workflows | XLSX exports/imports and event PDF exports | Preserve both capabilities; integrate reports separately |

Manifest versions above describe supplied files, not verified registry availability. The ZIP has no dependency lockfile or automated test suite in its archive listing. Do not copy its package manifest into TemplateOS.

### Baseline checks

- `npm run build:frontend`: passed TypeScript compilation and Vite production build. Existing warning: main JS chunk is approximately 515 kB minified. Lazy-load attendance routes and report dependencies when introduced.
- `backend/.venv/bin/python -m pytest -q` (invoked from backend as `.venv/bin/python -m pytest -q`): could not start because this environment has no `pytest`. Backend baseline remains unverified; install the declared development dependencies and run isolated tests in Phase 2.
- No source edits, dependency installs, database migrations, or remote database connections were performed in discovery. The attendance application was not launched because its startup code creates remote login records automatically.
- Final tracked diff still consists only of the pre-existing `package-lock.json` modification. Production build outputs are ignored by Git.
- No `graphify-out/` graph was present; no graph query or update was required for this documentation-only phase.

## Feature Inventory

| Workflow | Source reference | Intended destination |
| --- | --- | --- |
| Student dashboard and own request history | `src/components/StudentPortal.tsx` | Attendance overview and requests |
| Multi-item, multi-date correction requests with faculty/subject selection | Student portal, request types | Student request editor with backend validation |
| Edit/delete pending requests | Student portal, database service | Owner-only pending-request operations |
| Event creation and attendee search by PRN/name | `src/components/OrganiserPortal.tsx` | Events list and event detail |
| Save attendance draft and submit attendance | Organiser portal, database service | Transactional event attendance operations |
| Students, faculty, subjects master data | `src/components/AdminPortal.tsx` | Attendance administration |
| Whole-request and per-item review, partial approval, comments | Admin portal, request types | Review queue and request detail |
| Attendance percentage adjustment | Admin portal, database service | Restricted update with audit history |
| Filters, sorting, pagination, missing-percentage handling | `queryAttendanceReports` | Server-filtered report endpoint |
| Student multi-file import, pasted lists, faculty import, sample files | `src/utils/exportImport.ts` | Validated import preview followed by explicit import |
| Multiple Excel report formats and event attendance PDF | Export utilities | Download actions using the same filtered data |
| Audit history | Database service, admin portal | Server-created, scoped audit records |

Source paths in this table are relative to the extracted attendance project.

## Findings That Affect Integration

1. **Authorization must move to the backend.** `App.tsx` restores a user object from localStorage and `handleRoleChange` constructs privileged identities in the browser. Supplied `firestore.rules` permit public reads and writes to core collections. These are findings about the supplied code; deployed Firebase rules were not inspected.
2. **Do not port legacy authentication.** `dbService.ts` initializes default users with plaintext passwords and authenticates admin/organiser credentials in the browser. Student credentials are derived from name/PRN. Use TemplateOS accounts and its existing password hashing instead.
3. **Universal student access needs a deliberate replacement.** The source universal account can select any student and view all requests. Default integrated behavior: students access only their own records; authorized staff may submit on behalf of a student with the actor and subject both recorded.
4. **Do not port automatic seeding or database reset controls.** The source initializes remote records on startup and includes a function that clears all collections. Neither belongs in the integrated app's normal UI or startup path.
5. **UI code needs adaptation, not wholesale copying.** Portal files combine large amounts of state, forms, and data access. Split by workflow. Remove `.ts`/`.tsx` import suffixes where needed for host TypeScript settings, adapt Tailwind utilities, and verify each icon against the installed package.
6. **Data integrity cannot rely on the browser.** Validate ownership, dates, time ranges, percentage bounds, duplicate PRNs/attendees, valid referenced records, allowed state transitions, and concurrent review on the server. Audit writes should be part of the same transaction as business changes.
7. **Reports currently load and filter collections in the client.** Implement scope enforcement, filtering, sorting, and pagination in SQL. Exports must apply identical filters and permissions.
8. **Attendance percentages are recorded inputs in the source.** There is no demonstrated integration with an official timetable or attendance register. Do not claim approval automatically updates an institution's official attendance percentage.
9. **Do not change TemplateOS's global role meanings casually.** Existing template visibility depends on user roles. Attendance permissions must be separate checks; public signup must continue creating `normal_user`, without attendance privileges.

## Proposed Architecture

One TemplateOS app, one login, one API, one database. Attendance is a feature area under `/attendance/*`; it does not introduce another top-level navbar or login page.

### Bounded changes

- New frontend code under `frontend/src/features/attendance/` for pages, components, types, and API functions.
- Small host edits for lazy route registration, one sidebar entry, attendance page titles, and (if useful) exporting the existing API request helper. Avoid an auth-context rewrite.
- New attendance models, schemas, services, and endpoint files following the existing `backend/app/` organization.
- One attendance router registration in `backend/app/api/v1/api.py` and model registration as required by the existing migration setup.
- Additive Alembic migrations for attendance tables. No replacement of users, templates, or documents, and no destructive changes to existing data.
- Dependencies added only for demonstrated needs in the reports/import phase. No Firebase, second React installation, or second styling pipeline in the host app.

### Data design to specify in Phase 2

- Student profiles: PRN, semester, section, status, nullable unique link to an existing TemplateOS user. Imported roster entries may exist before an account is linked; linking must require authorized verification, not a student claiming an arbitrary PRN.
- Faculty and subject reference records, distinct from authentication accounts.
- Events with owning user, date/time, venue, status, and scope.
- Event attendees with a unique event/student pair and nullable attendance percentage where appropriate.
- Requests, request items, and explicit date records or an equivalent validated date representation.
- Review state, actor, timestamps, comments, and concurrency protection.
- Append-only audit records written by the server.
- Organization/department scope must be defined before endpoints are exposed. TemplateOS currently stores these as nullable strings; avoid introducing an unrelated tenancy rewrite. Fail closed when required scope is missing.
- Preserve historical report meaning when names or roster details change; settle snapshot versus live-reference fields in the schema contract.

### Proposed permission mapping, to finalize in Phase 2

| Existing role | Attendance capability proposal |
| --- | --- |
| `student` | Own linked profile and requests only |
| `faculty` | Organise own events and maintain their attendance within authorized scope |
| `department_admin` | Manage and review attendance for own department |
| `org_admin` | Manage and review attendance within own organization |
| `super_admin` | Attendance administration across scopes |
| `approver` | Review only within an explicitly assigned scope; deny access without it |
| `normal_user` | No attendance access by default |

Faculty acting as organisers, approval delegation, and staff submitting on behalf of students are product-policy decisions, not permissions inferred from the source's browser role selector.

## Delivery Phases and Parts

Stop at each review checkpoint rather than implementing the entire table in one pass. Report completed work, validation, and remaining issues before moving to the next part.

| Phase | Parts | Completion checkpoint |
| --- | --- | --- |
| 1. Discovery | Extract, inspect, inventory, baseline, plan | Complete; backend test baseline explicitly unverified |
| 2. Integration contract | 2A: complete (209 tests pass). 2B: complete (permissions contract saved). 2C: complete (schema, API, state machines, and screen map specified) | Complete contract established in PHASE-2C-CONTRACT.md |
| 3. Attendance foundation | 3A: additive schema and permission checks. 3B: student/faculty/subject APIs. 3C: lazily loaded Attendance section and reference-data screens | Migrations verified in disposable DB, access tests pass, existing app builds |
| 4. Core workflows | 4A: event creation and attendance drafts/submission. 4B: student request creation/history/editing. 4C: admin review and partial approval | Each workflow independently usable and tested, including denial and invalid-state cases |
| 5. Reports and imports | 5A: server-filtered reports. 5B: validated file/paste imports and duplicate handling. 5C: Excel/PDF exports and audit view | Preview matches committed import; exports match filters and permissions |
| 6. Polish and regression | 6A: cohesive desktop/mobile styling and accessibility. 6B: end-to-end role flows and original document/template regression. 6C: local demo and handoff | Browser-verified local experience, documented remaining limitations |

Visual polish is applied throughout; Phase 6 is the final pass, not the first time usability is considered. Prefer clear data tables, compact summaries, consistent form spacing, restrained status colors, and predictable navigation. Include loading, empty, validation, network-error, and permission-denied states. Use existing shared controls and keep styling scoped to avoid changing unrelated screens.

## Verification Requirements

- Establish the current backend baseline before attributing failures to integration. Use disposable test data, not the configured remote database.
- Test missing/expired tokens, cross-student access, cross-organiser edits, cross-department/organization access, unscoped users, and privilege escalation attempts.
- Test duplicate PRNs and attendees, date/time validity, optional versus zero percentage, bounds of 0-100, invalid foreign keys, repeated submissions, and conflicting reviews.
- Define aggregate request status from item decisions, including mixtures containing pending items. Do not allow browser-provided overall status to contradict item decisions.
- Test migration upgrade/downgrade on a disposable database, and verify PostgreSQL behavior as well as isolated unit/API tests before accepting database work.
- Verify event updates and audit entries commit atomically; test failures without partial writes.
- Verify spreadsheet leading-zero PRNs, duplicate rows across files, invalid rows, preview results, bounded imports, and exported report totals. Sanitize spreadsheet formula-like text on export.
- Verify desktop and mobile pages in a browser, keyboard focus, dialogs, horizontal tables, back/forward navigation, reload/deep links, and session expiry.
- Repeat original login, template upload/library, and document creation/edit flows at the integration checkpoint.
- Run production build and relevant regression tests for each implemented part. Record actual outcomes rather than promising zero issues.

## Next Part

Phase 3A: Attendance foundation — implement additive schema and SQLAlchemy models in `backend/app/models/attendance.py`, Alembic migration script, and capability dependency checks in `backend/app/api/deps.py`. Phases 1 and 2 (2A, 2B, 2C) are fully completed. Implementation follows strictly in small, verified steps per the working agreement.
