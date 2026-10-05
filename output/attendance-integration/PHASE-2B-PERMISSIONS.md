# Phase 2B: Attendance Permission Contract

Date: 2026-10-05 (Asia/Kolkata)
Result: permission draft reviewed. No code or schema changes.

---

## 1. Existing TemplateOS Roles and Authentication

### 1.1 Roles

Seven roles are defined in `backend/app/models/user.py`, enforced by a model-level `@validates("role")` guard:

| Role | Current use |
| --- | --- |
| `super_admin` | Full template access, template deletion |
| `org_admin` | Participates in organization-scoped template visibility |
| `department_admin` | Participates in department-scoped template visibility |
| `faculty` | Normal template features; no special privilege today |
| `student` | Normal template features; no special privilege today |
| `approver` | Normal template features; no special privilege today |
| `normal_user` | Default role assigned at public signup; template owner features |

### 1.2 Authentication

- **Signup**: public, always creates `normal_user` (`backend/app/api/v1/endpoints/auth.py`). Password is hashed with `pwdlib`.
- **Login**: email + password -> JWT with `sub = str(user.id)`. Token lifetime defaults to 60 minutes.
- **`get_current_user`**: extracts user ID from JWT `sub`, loads user from DB. No role is embedded in the token -- the full `User` row is fetched on every request (`backend/app/api/deps.py`).
- There is no admin endpoint to create users with elevated roles. Role assignment/change is currently a direct database operation.

### 1.3 Account Provisioning

- No admin API for role assignment or user management exists. A `super_admin` user must be seeded directly in the database.
- `department` and `organization` are nullable strings on the `User` model. They are used for template visibility scoping (`backend/app/services/template_access.py`), but there are no normalized organization or department tables -- they are free-text fields.
- No invitation or provisioning flow exists; all accounts are self-registered.

### 1.4 Template Visibility Dependencies

Template visibility uses the user's `role`, `department`, and `organization` fields:

| Visibility | Rule |
| --- | --- |
| `private` | Owner only |
| `public` | All authenticated users |
| `department` | Users whose `department` matches the uploader's `department` |
| `organization` | Users whose `organization` matches the uploader's `organization` |
| `group` | Users whose `role` matches the uploader's `role` |

> [!IMPORTANT]
> The `group` visibility compares `user.role`. If a `faculty` user's role is changed to something else, their templates' group visibility changes semantics. Attendance integration must not alter existing role values for users who have templates with `group` visibility.

---

## 2. TrackMyAttendance Reference Roles

The source app uses three browser-switchable roles with no server enforcement:

| Source role | Behavior |
| --- | --- |
| `STUDENT` | View/create/edit/delete own requests. Universal student account can act as any student. |
| `ORGANISER` | Create events, search students by PRN, save/submit attendance drafts |
| `ADMIN` | Full CRUD on students/faculty/subjects, review requests (approve/reject/partial), adjust attendance percentages, view reports, import/export, audit log, database reset |

**What we will not port** (confirmed in the user's working agreement):
- Browser role switching (`handleRoleChange` constructing privileged identities client-side)
- Plaintext default passwords hardcoded in the legacy client authentication flow
- Universal student access (`is_universal: true` that bypasses ownership)
- Automatic seeding (`initializeLoginDatabaseIfNeeded` creating default users on startup)
- Database-reset UI (`clearAllDatabaseData`)
- Firestore rules that allow public reads/writes to all collections

---

## 3. Attendance Permission Mapping

### 3.1 Role-to-Capability Matrix

Attendance permissions are **capability checks** layered on top of existing TemplateOS roles. They do not change what any role means for templates or documents. The existing `USER_ROLES` tuple is unchanged.

| TemplateOS role | Attendance capabilities | Scope boundary |
| --- | --- | --- |
| `student` | View own linked student profile. Create, edit, delete own pending requests. View own request history. | Own linked `att_student_profile` only |
| `faculty` | Create and manage own events. Save/submit attendance for own events. Search students by PRN/name within own department. | Own events only; student search within own department |
| `department_admin` | All faculty capabilities. Manage student/faculty/subject reference data for own department. Review requests from own department's students. View reports for own department. | Own department only |
| `org_admin` | All department_admin capabilities across all departments in own organization. Assign/revoke `department_admin` attendance access within own organization. | Own organization only |
| `super_admin` | All org_admin capabilities across all organizations. Assign/revoke `org_admin` attendance access. View global audit log. | Unrestricted |
| `approver` | Review attendance requests within an explicitly assigned scope. No other attendance access. | Explicitly assigned department(s) only; deny access without assignment |
| `normal_user` | No attendance access. | None |

### 3.2 Capability Definitions

Each capability is a server-enforced check, not a frontend conditional:

| Capability | Description | Required role(s) |
| --- | --- | --- |
| `attendance.student.own_profile` | View own linked student profile | `student` |
| `attendance.student.own_requests` | CRUD on own pending requests | `student` |
| `attendance.event.create` | Create new events | `faculty`, `department_admin`, `org_admin`, `super_admin` |
| `attendance.event.own_manage` | Edit/delete/submit own events | Event creator |
| `attendance.event.dept_view` | View events in own department | `department_admin`, `org_admin`, `super_admin` |
| `attendance.student_data.search` | Search students by PRN/name | `faculty` (own dept), `department_admin` (own dept), `org_admin` (own org), `super_admin` |
| `attendance.ref_data.manage` | CRUD students/faculty/subjects | `department_admin` (own dept), `org_admin` (own org), `super_admin` |
| `attendance.request.review` | Approve/reject/partial-approve | `department_admin` (own dept), `org_admin` (own org), `approver` (assigned scope), `super_admin` |
| `attendance.percentage.adjust` | Modify attendance percentage | `department_admin` (own dept), `org_admin` (own org), `super_admin` |
| `attendance.report.view` | View attendance reports | `faculty` (own events), `department_admin` (own dept), `org_admin` (own org), `super_admin` |
| `attendance.import` | Bulk import students/faculty | `department_admin` (own dept), `org_admin` (own org), `super_admin` |
| `attendance.export` | Export reports/event PDFs | Same as `attendance.report.view` |
| `attendance.audit.view` | View attendance audit log | `department_admin` (own dept), `org_admin` (own org), `super_admin` |
| `attendance.access.assign` | Assign attendance roles | `org_admin` (within org), `super_admin` |

### 3.3 Implementation Strategy

Capabilities will be implemented as a `require_attendance_capability(user, capability, scope)` dependency function in the backend, similar to the existing `get_current_user` pattern. This function:

1. Accepts the authenticated `User` object (already resolved by `get_current_user`).
2. Checks the user's role against the capability table.
3. For scoped capabilities, verifies the user's `department`/`organization` matches the target resource's scope.
4. Returns the user if permitted; raises `HTTPException(403)` otherwise.

This is additive. No change to `get_current_user`, `CurrentUser`, or the JWT structure.

---

## 4. Organization and Department Boundaries

### 4.1 Current State

- `User.department` and `User.organization` are nullable `String(255)` columns -- free-text, no foreign keys, no normalization.
- Template visibility for "department" and "organization" modes compares these strings between the template uploader and the viewing user.
- There are no `organizations` or `departments` tables.

### 4.2 Attendance Scope Rules

Attendance resources are scoped by department and organization strings stored on the owning user or the resource itself.

**Scope enforcement rules:**

| Rule | Behavior |
| --- | --- |
| Missing scope | If a user's `department` or `organization` is `NULL` or empty, attendance capabilities that require scope are **denied by default** (fail closed). A `faculty` with no department set cannot create events. |
| Case sensitivity | Department and organization comparisons are **case-insensitive** (server normalizes to lowercase for comparison). |
| Scope on resources | Attendance resources (student profiles, events, requests) store the `department` and `organization` of the creating user at creation time as snapshot fields. |
| Cross-department | A `department_admin` cannot see or act on attendance resources from other departments, even within the same organization. An `org_admin` can act across departments within their organization. |
| No tenancy rewrite | We do not introduce organization/department tables or foreign keys in Phase 2B. Scope remains string-based, matching existing User model semantics. If the project later normalizes these into tables, attendance scope checks need updating. |

### 4.3 Decision: Department Field on Attendance Resources

Every attendance resource (student profile, faculty record, subject, event, request) will carry a `department` string that is set at creation time from the creating user's department. This enables:
- Department-scoped queries without joining to the user table on every read.
- Historical accuracy (if an admin's department changes, their previously-created resources keep the original scope).

Events additionally carry an `organization` string for org-level reporting.

---

## 5. Student Account Linking

### 5.1 Problem

The attendance system needs **student profiles** (PRN, semester, section, name) that may be imported in bulk before any student creates a TemplateOS account. When a student does sign up, their account must be linked to the correct profile -- but a student should not be able to claim an arbitrary PRN.

### 5.2 Design

```
att_student_profiles
  id (PK)
  prn (UNIQUE, NOT NULL)
  full_name (NOT NULL)
  semester (NOT NULL)
  section (NOT NULL)
  department (NOT NULL)
  organization (nullable)
  status ('active' | 'inactive')
  user_id (FK -> users.id, UNIQUE, NULLABLE)  <-- the link
  linked_at (TIMESTAMP, NULLABLE)
  linked_by (FK -> users.id, NULLABLE)  <-- who authorized the link
  created_at, updated_at
```

### 5.3 Linking Rules

| Rule | Description |
| --- | --- |
| **Who creates profiles** | `department_admin` (own dept), `org_admin` (own org), `super_admin`, or bulk import |
| **Who links** | A `department_admin`, `org_admin`, or `super_admin` -- never the student themselves |
| **Link verification** | The admin selects an existing TemplateOS `User` (by email lookup) and links them to a student profile. The system records `linked_by` and `linked_at`. |
| **Self-claim prevention** | Students cannot link themselves to a profile. There is no endpoint for "claim this PRN". |
| **Role requirement** | The linked user account must have role `student`. If the user's role is not `student`, the link is rejected. |
| **Duplicate prevention** | `user_id` is UNIQUE -- one user can link to at most one student profile. `prn` is UNIQUE -- one PRN maps to exactly one profile. |
| **Unlinking** | Same authorized roles can unlink. Unlinking sets `user_id`, `linked_at`, `linked_by` to NULL. Existing requests/attendance records retain the `student_profile_id` FK (they don't break). |
| **Profile without account** | Valid. Imported roster entries exist before any user signs up. Such profiles appear in reports and can receive attendance records (via organiser event attendance), but no one can log in and see "my requests" for that profile until linked. |
| **Account without profile** | A `student`-role user without a linked profile sees an empty attendance section with a message: "Your student profile has not been linked yet. Contact your department administrator." |

### 5.4 Handling Duplicate and Conflicting Data

| Scenario | Resolution |
| --- | --- |
| Import contains duplicate PRN within the same file | Reject the duplicate row; report it in import preview |
| Import PRN matches an existing profile | Skip (do not overwrite); report as "already exists" |
| Two imports from different departments with same PRN | PRN is globally unique -- second import is rejected |
| Student name on profile != linked user's `full_name` | Keep both. Profile `full_name` is the roster name; user `full_name` is the account name. Reports use the profile name. The admin can update the profile name if needed. |
| Linked user account is deleted | Profile remains, `user_id` becomes orphaned. Attendance migration should handle this with `ON DELETE SET NULL` on the FK. |

---

## 6. Access Assignment and Revocation

### 6.1 Who Can Assign Attendance Roles

TemplateOS roles are global (they affect template visibility). Attendance capabilities are derived from these roles, so changing a user's role has both template and attendance implications.

| Action | Who may perform | Constraints |
| --- | --- | --- |
| Change user role to `student` | `department_admin`, `org_admin`, `super_admin` | User must not have templates with `group` visibility (or change would alter template access semantics) |
| Change user role to `faculty` | `department_admin` (own dept), `org_admin`, `super_admin` | Same constraint |
| Change user role to `department_admin` | `org_admin` (own org), `super_admin` | Target user must have `department` set |
| Change user role to `org_admin` | `super_admin` only | Target user must have `organization` set |
| Change user role to `approver` | `org_admin`, `super_admin` | Requires explicit scope assignment (see 6.2) |
| Revoke elevated role (set back to `normal_user`) | Same level that granted it | Audit logged |

> [!WARNING]
> Changing a user's role changes their template `group` visibility scope. Before any role change, the system must check: does this user own templates with `visibility = 'group'`? If yes, warn the admin that those templates' visibility will change semantics. The API must require explicit confirmation (`confirm: true` flag) to proceed.

### 6.2 Approver Scope Assignment

The `approver` role alone is insufficient -- an approver must also have explicitly assigned department(s) to review. This requires a small join table:

```
att_approver_scopes
  id (PK)
  user_id (FK -> users.id, NOT NULL)
  department (NOT NULL)
  assigned_by (FK -> users.id, NOT NULL)
  assigned_at (TIMESTAMP)
```

- An `approver` with no rows in `att_approver_scopes` has **zero** attendance review access.
- An `org_admin` can assign departments within their organization.
- A `super_admin` can assign any department.
- This table is purely additive; it does not change existing behavior.

### 6.3 Decision: No Attendance-Specific Role Column

We do not add a second `attendance_role` column to the `User` model. Attendance capabilities are derived from the existing `role` column plus scope checks. This avoids:
- Two parallel role systems that can conflict
- Migration complexity for existing users
- Template visibility regressions

If future requirements need finer-grained attendance permissions that don't map to TemplateOS roles, a separate `att_user_permissions` table can be introduced then.

---

## 7. Record Ownership

### 7.1 Who Owns What

| Resource | Owner | Ownership field |
| --- | --- | --- |
| Student profile | The department that imported/created it | `department` string |
| Faculty record | The department that created it | `department` string |
| Subject record | The department that created it | `department` string |
| Event | The user who created it | `created_by` FK -> `users.id` |
| Event attendance record | The event (inherits event's owner) | `event_id` FK |
| Attendance request | The student profile | `student_profile_id` FK |
| Request items | The request | `request_id` FK |
| Audit log entry | The system (immutable) | `actor_user_id` FK |

### 7.2 Ownership Transfer

Ownership transfer is not supported in Phase 2B. If an organiser leaves, their events remain attributed to them. A `super_admin` can reassign events in a future phase if needed.

---

## 8. Assumptions

1. **One student profile per user.** A user account maps to at most one student profile. Multi-profile scenarios (e.g., a student in two departments) are out of scope.
2. **Department is mandatory for attendance participation.** Users without a `department` string set on their account cannot use scoped attendance features (fail closed).
3. **Organization is optional but recommended.** Cross-department features (org_admin, org-level reports) require `organization` to be set.
4. **No role hierarchy in the database.** Role comparison is flat string matching, not a tree. `super_admin` checks are explicit `== "super_admin"` guards, not "is at least admin".
5. **PRN format is opaque.** The system treats PRN as a case-sensitive string. Leading zeros from spreadsheet imports must be preserved (import validation in Phase 5).
6. **Attendance percentage is a recorded input, not computed.** The system stores what the organiser/admin enters. It does not integrate with an official timetable or attendance register.
7. **Concurrent review protection.** When two admins review the same request, the second reviewer must see the first reviewer's decision. This will be specified in Phase 2C (optimistic concurrency via `updated_at` check).
8. **Audit writes are transactional.** Audit records for business changes are written in the same database transaction -- not as fire-and-forget background tasks.
9. **No cascading role changes.** Changing a user's role does not automatically update their attendance resources. A faculty->normal_user change does not delete their events; it prevents them from creating new ones.

---

## 9. Permission Test Scenarios

These scenarios will be codified as automated tests in Phase 3A.

### 9.1 Authentication and Basic Access

| # | Scenario | Expected result |
| --- | --- | --- |
| T1 | Unauthenticated request to any `/attendance/*` endpoint | 401 |
| T2 | `normal_user` accesses `/attendance/dashboard` | 403 |
| T3 | `student` without linked profile accesses attendance | 200, empty dashboard with "profile not linked" message |
| T4 | `student` with linked profile accesses own requests | 200, sees own requests |
| T5 | Expired JWT on attendance endpoint | 401 |

### 9.2 Student Boundary Enforcement

| # | Scenario | Expected result |
| --- | --- | --- |
| T6 | Student A tries to view Student B's requests | 403 |
| T7 | Student A tries to edit Student B's pending request | 403 |
| T8 | Student A tries to delete Student B's pending request | 403 |
| T9 | Student edits own request that is already `approved` | 403 (only `pending` requests are editable) |
| T10 | Student deletes own request that is already `rejected` | 403 (only `pending` requests are deletable) |

### 9.3 Faculty/Organiser Boundary Enforcement

| # | Scenario | Expected result |
| --- | --- | --- |
| T11 | Faculty without `department` set tries to create event | 403 (fail closed) |
| T12 | Faculty creates event in own department | 201 |
| T13 | Faculty tries to edit another faculty's event | 403 |
| T14 | Faculty tries to submit attendance for another's event | 403 |
| T15 | Faculty searches students outside own department | 200, empty results (scoped query) |

### 9.4 Department Admin Boundary Enforcement

| # | Scenario | Expected result |
| --- | --- | --- |
| T16 | `department_admin` reviews request from own department | 200 |
| T17 | `department_admin` reviews request from different department | 403 |
| T18 | `department_admin` creates student profile for own department | 201 |
| T19 | `department_admin` creates student profile for other department | 403 |
| T20 | `department_admin` imports students for own department | 200 |
| T21 | `department_admin` imports students for other department | 403 |

### 9.5 Org Admin Boundary Enforcement

| # | Scenario | Expected result |
| --- | --- | --- |
| T22 | `org_admin` reviews request from own organization, different department | 200 |
| T23 | `org_admin` reviews request from different organization | 403 |
| T24 | `org_admin` assigns `department_admin` within own org | 200 |
| T25 | `org_admin` assigns `department_admin` in different org | 403 |

### 9.6 Approver Scoped Access

| # | Scenario | Expected result |
| --- | --- | --- |
| T26 | `approver` with no scope assignments | 403 on all attendance review |
| T27 | `approver` with scope for Dept A reviews Dept A request | 200 |
| T28 | `approver` with scope for Dept A reviews Dept B request | 403 |
| T29 | `approver` tries to create/manage events | 403 |
| T30 | `approver` tries to manage reference data | 403 |

### 9.7 Super Admin

| # | Scenario | Expected result |
| --- | --- | --- |
| T31 | `super_admin` accesses any attendance resource | 200 |
| T32 | `super_admin` reviews request from any department | 200 |
| T33 | `super_admin` assigns `org_admin` | 200 |

### 9.8 Student Account Linking

| # | Scenario | Expected result |
| --- | --- | --- |
| T34 | Student tries to link themselves to a profile | 403 |
| T35 | `department_admin` links a `student`-role user to profile in own dept | 200 |
| T36 | `department_admin` links a `normal_user`-role user to profile | 400 (user must be `student` role) |
| T37 | `department_admin` links user already linked to another profile | 409 (one link per user) |
| T38 | `department_admin` links to a profile that already has a linked user | 409 (one link per profile) |
| T39 | `department_admin` links to profile in different department | 403 |
| T40 | `department_admin` unlinks a student in own dept | 200; profile retains history |

### 9.9 Role Change Safety

| # | Scenario | Expected result |
| --- | --- | --- |
| T41 | Change role of user with `group`-visibility templates without `confirm` | 400 (must confirm) |
| T42 | Change role of user with `group`-visibility templates with `confirm: true` | 200 (proceeds with warning) |
| T43 | Change role of user with only `private` templates | 200 (no warning needed) |

### 9.10 Privilege Escalation Attempts

| # | Scenario | Expected result |
| --- | --- | --- |
| T44 | `student` sends crafted request body with `role: "super_admin"` to attendance endpoint | Ignored; role is read from the authenticated user's DB row |
| T45 | Tampered JWT with different `sub` | 401 (signature verification fails) |
| T46 | `faculty` tries to access admin-only attendance management | 403 |

---

## 10. Product Decisions Still Required

Antigravity drafted Phase 2C before these product choices were confirmed. Phase 2C therefore remains a draft. Conservative defaults are recorded below so implementation does not accidentally expand scope:

1. **Admin user management API.** TemplateOS has no admin endpoint for changing user roles. Default: defer global role mutation and use the existing local seed tooling until a separate user-administration design is approved. Attendance scope endpoints must not silently become a global role editor.

2. **First super_admin bootstrap.** The existing `backend/scripts/seed_user.py` supports creating a `super_admin`. Default: retain it and do not add another bootstrap path.

3. **Department string normalization.** Departments are free-text. Default: trim/collapse whitespace on write and compare case-insensitively. Aliases such as "CS" and "Computer Science" remain distinct until normalized scope tables are explicitly approved.

4. **Multi-department faculty.** Default: one department per user for the first attendance release. Multi-department membership requires a later identity/scope redesign.

5. **Approver notification.** Default: provide a review queue without notifications. Notification infrastructure is outside the first integration scope.

---

## 11. Decisions Log

| # | Decision | Rationale |
| --- | --- | --- |
| D1 | Attendance capabilities derive from existing TemplateOS roles | Avoids dual-role system; keeps `USER_ROLES` unchanged |
| D2 | No attendance-specific role column | Prevents conflicts between role systems |
| D3 | Fail closed when scope is missing | A faculty without department cannot create events -- safer than defaulting to global access |
| D4 | Student self-linking is prohibited | Prevents PRN spoofing; admin verification required |
| D5 | PRN is globally unique, not per-department | Simpler constraint; matches real-world PRN assignment |
| D6 | Approver requires explicit scope assignment | Prevents approver role from being a backdoor to all departments |
| D7 | Department/organization remain free-text strings | Matches existing User model; avoids migration risk |
| D8 | Role changes require confirmation when `group`-visibility templates exist | Protects existing template sharing semantics |
| D9 | Resources snapshot scope at creation time | Historical accuracy; admin department changes don't retroactively change resource visibility |
| D10 | Audit writes are same-transaction as business changes | Prevents partial writes where business change commits but audit doesn't |
