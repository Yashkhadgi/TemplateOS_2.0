# Phase 2C: Schema, API, State Machine, and Screen Specification

Date: 2026-10-05 (Asia/Kolkata)
Status: Draft reviewed after Antigravity handoff. Resolve the review notes below before implementation.

---

## 1. Overview & System Principles

This document defines the technical integration contract between the **TemplateOS** application platform and the incoming **TrackMyAttendance** subsystem.

### Review Notes Before Implementation

- Phase 2B product choices were not confirmed before this document was drafted; conservative defaults are now recorded there.
- Event administration is inconsistent: some sections restrict edits to the creator while the screen matrix lets scoped administrators take attendance. Choose one server-side rule before building endpoints.
- The API list is incomplete for the promised feature inventory: master-data update/delete, event deletion, imports, percentage adjustment, role/scope administration, and dashboard summary endpoints still need contracts.
- `att_approver_scopes` must avoid collisions when different organizations use the same department name. Require organization scope and include it in uniqueness and authorization checks.
- Free-text department/organization fields require one canonical write/compare policy. UI labels are not an authorization boundary.
- Derive request aggregate status entirely from item decisions; accepting an independent `overall_status` can create contradictory payloads.
- Validate exact PostgreSQL/Alembic types and downgrade behavior in a disposable database before accepting migration code.

### Core Architectural Invariants
1. **Single Application, Single Database**: Attendance is a module under `/api/v1/attendance` and `/attendance/*`. It does not use Firestore, Firebase Auth, or a separate database.
2. **Additive Only**: No existing tables (`users`, `templates`, `template_fields`, `documents`, `document_values`, `ai_generations`) or their columns are altered. No foreign keys are placed onto existing tables that would cause breaking cascade behavior.
3. **Strict Capability Scoping**: All operations verify permissions on the server via `require_attendance_capability` (established in [Phase 2B](PHASE-2B-PERMISSIONS.md)). Client-side guards are strictly for UX.
4. **Historical Immutability & Snapshots**: Master data changes (e.g. student name correction, faculty title) must never retroactively corrupt past event registers or approved correction requests. Snapshot columns capture identity at transaction time, while foreign keys preserve relational links.
5. **Atomic Audit Logging**: Any mutating action (event submission, request review, percentage adjustment, profile linking) must insert an audit record in the **same database transaction**.

---

## 2. Relational Database Schema Specification

All tables use the `att_` prefix to isolate attendance resources cleanly within the shared PostgreSQL database.

### 2.1 Entity Relationship Diagram

```
                 +-------------------+
                 |       users       | (Existing TemplateOS table)
                 +-------------------+
                   ^       ^       ^
                   |       |       |
      user_id (FK) |       |       | (FK: creator, reviewer, actor)
                   |       |       |
+--------------------------+ | +------------------------+
|   att_student_profiles   | | |  att_approver_scopes   |
+--------------------------+ | +------------------------+
       ^              ^      |
       |              |      |
(FK)   |         (FK) |      +--------------------+
       |              |                           |
+--------------+ +---------------------+ +------------------+ +-----------------+
| att_event_   | |    att_requests     | |    att_events    | | att_audit_logs  |
| attendees    | +---------------------+ +------------------+ +-----------------+
+--------------+           |                      |
       ^                   | (FK)                 | (FK)
       |                   v                      v
       |         +---------------------+ +------------------+
       |         |  att_request_items  | | att_event_       |
       |         +---------------------+ | attendees        |
       |                   |             +------------------+
       |                   v (FK)
       |         +---------------------+
       |         |att_request_item_    |
       |         |dates                |
       |         +---------------------+
       |
+--------------+ +---------------------+
| att_faculty  | |    att_subjects     |
+--------------+ +---------------------+
```

---

### 2.2 Table Definitions & DDL

#### 2.2.1 `att_student_profiles`
Stores student academic roster identity. Can exist prior to user account registration.

| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key, Auto-increment | Internal surrogate key |
| `prn` | `VARCHAR(64)` | NO | UNIQUE, INDEX | Permanent Registration Number |
| `full_name` | `VARCHAR(255)` | NO | | Official student name |
| `semester` | `INTEGER` | NO | CHECK (`semester` BETWEEN 1 AND 12) | Academic semester |
| `section` | `VARCHAR(32)` | NO | | Class section (e.g., "A", "B", "CS-1") |
| `department` | `VARCHAR(255)` | NO | INDEX | Normalized department name |
| `organization` | `VARCHAR(255)` | YES | INDEX | Normalized organization name |
| `status` | `VARCHAR(32)` | NO | DEFAULT `'active'`, CHECK in (`'active'`, `'inactive'`) | Academic enrollment status |
| `user_id` | `INTEGER` | YES | UNIQUE, FK -> `users(id)` ON DELETE SET NULL | Linked TemplateOS user account |
| `linked_at` | `TIMESTAMPTZ` | YES | | Timestamp of account linking |
| `linked_by` | `INTEGER` | YES | FK -> `users(id)` ON DELETE SET NULL | Admin user who authorized link |
| `created_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Row creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Last updated timestamp |

*Indexes*:
- `ix_att_student_profiles_prn` (UNIQUE)
- `ix_att_student_profiles_dept_sem_sec` (`department`, `semester`, `section`)
- `ix_att_student_profiles_user_id` (`user_id`)

---

#### 2.2.2 `att_faculty`
Master directory of faculty members for event and correction tagging.

| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key, Auto-increment | Internal surrogate key |
| `name` | `VARCHAR(255)` | NO | | Faculty full name |
| `department` | `VARCHAR(255)` | NO | INDEX | Owning department |
| `organization` | `VARCHAR(255)` | YES | INDEX | Owning organization |
| `email` | `VARCHAR(255)` | YES | | Optional institutional contact email |
| `status` | `VARCHAR(32)` | NO | DEFAULT `'active'`, CHECK in (`'active'`, `'inactive'`) | Active status |
| `created_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Last updated timestamp |

*Indexes*:
- `ix_att_faculty_dept_name` (`department`, `name`)

---

#### 2.2.3 `att_subjects`
Course and subject catalog used in attendance correction requests.

| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key, Auto-increment | Internal surrogate key |
| `name` | `VARCHAR(255)` | NO | | Subject title (e.g. "Data Structures") |
| `code` | `VARCHAR(64)` | NO | | Course code (e.g. "CS201") |
| `department` | `VARCHAR(255)` | NO | INDEX | Department offering subject |
| `organization` | `VARCHAR(255)` | YES | INDEX | Organization scope |
| `status` | `VARCHAR(32)` | NO | DEFAULT `'active'`, CHECK in (`'active'`, `'inactive'`) | Subject active status |
| `created_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Last updated timestamp |

*Constraints*:
- UNIQUE (`code`, `department`)
*Indexes*:
- `ix_att_subjects_dept_code` (`department`, `code`)

---

#### 2.2.4 `att_events`
Institutional events, guest lectures, hackathons, or workshops where attendance is taken.

| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key, Auto-increment | Internal surrogate key |
| `title` | `VARCHAR(255)` | NO | | Event title |
| `event_date` | `DATE` | NO | INDEX | Date event took place |
| `start_time` | `TIME` | NO | | Scheduled start time |
| `end_time` | `TIME` | NO | | Scheduled end time |
| `venue` | `VARCHAR(255)` | NO | | Physical venue or room |
| `description` | `TEXT` | YES | | Detailed notes or event brief |
| `organiser_id` | `INTEGER` | NO | FK -> `users(id)` ON DELETE RESTRICT | Creator and organiser user |
| `department` | `VARCHAR(255)` | NO | INDEX | Snapshot creator department |
| `organization` | `VARCHAR(255)` | YES | INDEX | Snapshot creator organization |
| `status` | `VARCHAR(32)` | NO | DEFAULT `'draft'`, CHECK in (`'draft'`, `'submitted'`) | Event attendance status |
| `student_count` | `INTEGER` | NO | DEFAULT 0 | Cached count of attendees |
| `submitted_at` | `TIMESTAMPTZ` | YES | | Timestamp of final submission |
| `created_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Record update timestamp |

*Constraints*:
- CHECK (`end_time` > `start_time`)
*Indexes*:
- `ix_att_events_organiser` (`organiser_id`)
- `ix_att_events_dept_date` (`department`, `event_date`)

---

#### 2.2.5 `att_event_attendees`
Participant attendance records for an event.

| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key, Auto-increment | Internal surrogate key |
| `event_id` | `INTEGER` | NO | FK -> `att_events(id)` ON DELETE CASCADE | Parent event |
| `student_profile_id` | `INTEGER` | NO | FK -> `att_student_profiles(id)` ON DELETE RESTRICT | Target student profile |
| `prn_snapshot` | `VARCHAR(64)` | NO | | Snapshot PRN at event time |
| `name_snapshot` | `VARCHAR(255)` | NO | | Snapshot student name |
| `semester_snapshot` | `INTEGER` | NO | | Snapshot semester |
| `section_snapshot` | `VARCHAR(32)` | NO | | Snapshot section |
| `current_attendance_percentage`| `NUMERIC(5,2)` | YES | CHECK (`current_attendance_percentage` BETWEEN 0.00 AND 100.00) | Recorded percentage at event time |
| `created_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Attendance entry time |

*Constraints*:
- UNIQUE (`event_id`, `student_profile_id`)
*Indexes*:
- `ix_att_event_attendees_event` (`event_id`)
- `ix_att_event_attendees_profile` (`student_profile_id`)
- `ix_att_event_attendees_prn` (`prn_snapshot`)

---

#### 2.2.6 `att_requests`
Attendance correction/update requests submitted by or on behalf of students.

| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key, Auto-increment | Internal surrogate key |
| `student_profile_id` | `INTEGER` | NO | FK -> `att_student_profiles(id)` ON DELETE RESTRICT | Student requesting adjustment |
| `prn_snapshot` | `VARCHAR(64)` | NO | | Student PRN snapshot |
| `name_snapshot` | `VARCHAR(255)` | NO | | Student name snapshot |
| `semester_snapshot` | `INTEGER` | NO | | Student semester snapshot |
| `section_snapshot` | `VARCHAR(32)` | NO | | Student section snapshot |
| `department` | `VARCHAR(255)` | NO | INDEX | Request department scope |
| `organization` | `VARCHAR(255)` | YES | INDEX | Request organization scope |
| `current_attendance_percentage`| `NUMERIC(5,2)` | YES | CHECK (`current_attendance_percentage` BETWEEN 0.00 AND 100.00) | Snapshot baseline percentage |
| `status` | `VARCHAR(32)` | NO | DEFAULT `'pending'`, CHECK in (`'pending'`, `'approved'`, `'rejected'`, `'partially_approved'`) | Aggregate review status |
| `admin_comment` | `TEXT` | YES | | Reviewer decision notes |
| `reviewed_by` | `INTEGER` | YES | FK -> `users(id)` ON DELETE SET NULL | Reviewer user ID |
| `reviewed_at` | `TIMESTAMPTZ` | YES | | Timestamp of review |
| `submitted_by` | `INTEGER` | NO | FK -> `users(id)` ON DELETE RESTRICT | User submitting the request |
| `version` | `INTEGER` | NO | DEFAULT 1 | Optimistic concurrency counter |
| `created_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Submission timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Last state change timestamp |

*Indexes*:
- `ix_att_requests_student` (`student_profile_id`)
- `ix_att_requests_dept_status` (`department`, `status`)
- `ix_att_requests_created` (`created_at` DESC)

---

#### 2.2.7 `att_request_items`
Detailed line items within a request specifying particular subjects/lectures missed.

| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key, Auto-increment | Internal surrogate key |
| `request_id` | `INTEGER` | NO | FK -> `att_requests(id)` ON DELETE CASCADE | Parent request |
| `event_title` | `VARCHAR(255)` | NO | | Title of conflicting event/reason |
| `subject_id` | `INTEGER` | YES | FK -> `att_subjects(id)` ON DELETE SET NULL | Target subject |
| `subject_name_snapshot` | `VARCHAR(255)` | NO | | Subject name snapshot |
| `faculty_id` | `INTEGER` | YES | FK -> `att_faculty(id)` ON DELETE SET NULL | Assigned faculty |
| `faculty_name_snapshot` | `VARCHAR(255)` | NO | | Faculty name snapshot |
| `start_time` | `TIME` | NO | | Lecture start time |
| `end_time` | `TIME` | NO | | Lecture end time |
| `reason` | `TEXT` | NO | | Reason for absence/correction |
| `status` | `VARCHAR(32)` | NO | DEFAULT `'pending'`, CHECK in (`'pending'`, `'approved'`, `'rejected'`) | Decision on this specific item |
| `admin_note` | `TEXT` | YES | | Reviewer note for this item |
| `created_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Item decision timestamp |

*Constraints*:
- CHECK (`end_time` > `start_time`)
*Indexes*:
- `ix_att_request_items_req` (`request_id`)

---

#### 2.2.8 `att_request_item_dates`
Normalized dates associated with each request line item (supporting multi-date requests).

| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key, Auto-increment | Internal surrogate key |
| `item_id` | `INTEGER` | NO | FK -> `att_request_items(id)` ON DELETE CASCADE | Parent item |
| `date_value` | `DATE` | NO | INDEX | Specific date for attendance |

*Constraints*:
- UNIQUE (`item_id`, `date_value`)

---

#### 2.2.9 `att_approver_scopes`
Explicit departmental scope assignments for users holding the `approver` role.

| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key, Auto-increment | Internal surrogate key |
| `user_id` | `INTEGER` | NO | FK -> `users(id)` ON DELETE CASCADE | Approver user account |
| `department` | `VARCHAR(255)` | NO | INDEX | Assigned department name |
| `organization` | `VARCHAR(255)` | YES | INDEX | Organization context |
| `assigned_by` | `INTEGER` | NO | FK -> `users(id)` ON DELETE RESTRICT | Admin granting scope |
| `assigned_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP` | Assignment timestamp |

*Constraints*:
- UNIQUE (`user_id`, `department`)

---

#### 2.2.10 `att_audit_logs`
Immutable audit log recording every state transition, percentage change, and administrative action.

| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | NO | Primary Key, Auto-increment | Internal surrogate key |
| `actor_user_id` | `INTEGER` | NO | FK -> `users(id)` ON DELETE RESTRICT | Acting user account |
| `actor_name` | `VARCHAR(255)` | NO | | Snapshot actor name |
| `actor_role` | `VARCHAR(50)` | NO | | Snapshot actor role |
| `action` | `VARCHAR(100)` | NO | INDEX | Action description |
| `entity` | `VARCHAR(64)` | NO | INDEX | Target entity table |
| `entity_id` | `VARCHAR(64)` | NO | INDEX | Target entity ID |
| `department` | `VARCHAR(255)` | YES | INDEX | Scope department |
| `organization` | `VARCHAR(255)` | YES | INDEX | Scope organization |
| `old_value` | `TEXT` | YES | | Previous state or JSON summary |
| `new_value` | `TEXT` | YES | | New state or JSON summary |
| `created_at` | `TIMESTAMPTZ` | NO | DEFAULT `CURRENT_TIMESTAMP`, INDEX | Timestamp of event |

---

## 3. API Endpoints Specification

All endpoints are mounted under `/api/v1/attendance`. All routes require authentication (`Authorization: Bearer <token>`) and validate role/scope via `require_attendance_capability`.

### 3.1 Student Profiles & Account Linking (`/students`)

#### 1. `GET /api/v1/attendance/students/me`
- **Description**: Returns the authenticated student's linked profile and summary.
- **Capability**: `attendance.student.own_profile` (`student` role).
- **Responses**:
  - `200 OK`: `StudentProfileResponse`
  - `404 Not Found`: `{ "detail": "No student profile is linked to this account." }`

#### 2. `GET /api/v1/attendance/students`
- **Description**: Query/search student roster entries within caller scope.
- **Capability**: `attendance.student_data.search` (`faculty`, `department_admin`, `org_admin`, `super_admin`).
- **Query Params**:
  - `query`: Optional search string matching PRN or Name (case-insensitive prefix/containment).
  - `semester`: Optional integer filter.
  - `section`: Optional string filter.
  - `department`: Optional string (enforced by caller scope; faculty/dept_admin cannot query outside own department).
  - `status`: Optional `'active'` | `'inactive'` (default `'active'`).
  - `page`: Integer (default 1).
  - `page_size`: Integer (default 50, max 200).
- **Responses**:
  - `200 OK`: `PaginatedResponse[StudentProfileResponse]`

#### 3. `POST /api/v1/attendance/students`
- **Description**: Create a single student roster profile.
- **Capability**: `attendance.ref_data.manage` (`department_admin`, `org_admin`, `super_admin`).
- **Request Body**: `StudentProfileCreateRequest`
  - `prn`: string (required)
  - `full_name`: string (required)
  - `semester`: integer (1-12)
  - `section`: string
  - `department`: string (must match admin department unless super_admin)
- **Responses**:
  - `201 Created`: `StudentProfileResponse`
  - `409 Conflict`: PRN already exists in database.

#### 4. `POST /api/v1/attendance/students/{id}/link`
- **Description**: Link a registered TemplateOS user account to a student roster profile.
- **Capability**: `attendance.ref_data.manage` (`department_admin`, `org_admin`, `super_admin`).
- **Request Body**: `LinkStudentAccountRequest`
  - `user_id`: integer (User must have role `student`)
- **Validation**:
  - Target user must exist and have `role == 'student'`.
  - Target user must not already be linked to another profile (`409 Conflict`).
  - Target profile must not already have a linked user (`409 Conflict`).
  - Department of profile must match caller's scope (`403 Forbidden`).
- **Responses**:
  - `200 OK`: `StudentProfileResponse`

#### 5. `DELETE /api/v1/attendance/students/{id}/link`
- **Description**: Unlink a user account from a student profile.
- **Capability**: `attendance.ref_data.manage`.
- **Responses**:
  - `200 OK`: `StudentProfileResponse` (`user_id` set to null).

---

### 3.2 Master Catalog: Faculty & Subjects (`/faculty`, `/subjects`)

#### 1. `GET /api/v1/attendance/faculty`
- **Description**: List faculty members within caller's scope.
- **Capability**: `attendance.event.create` or `attendance.student.own_requests` (students can select faculty for correction requests).
- **Query Params**: `department` (optional), `status` (default `'active'`).
- **Responses**: `200 OK`: `list[FacultyResponse]`

#### 2. `POST /api/v1/attendance/faculty`
- **Capability**: `attendance.ref_data.manage`.
- **Request Body**: `FacultyCreateRequest` (`name`, `department`, `email`).
- **Responses**: `201 Created`: `FacultyResponse`

#### 3. `GET /api/v1/attendance/subjects`
- **Description**: List subjects within caller's department/scope.
- **Capability**: Any attendance participant.
- **Responses**: `200 OK`: `list[SubjectResponse]`

#### 4. `POST /api/v1/attendance/subjects`
- **Capability**: `attendance.ref_data.manage`.
- **Request Body**: `SubjectCreateRequest` (`name`, `code`, `department`).
- **Responses**: `201 Created`: `SubjectResponse`

---

### 3.3 Events & Event Attendance (`/events`)

#### 1. `GET /api/v1/attendance/events`
- **Description**: List events. Faculty see own events; admins see department/org events.
- **Capability**: `attendance.event.create` or `attendance.event.dept_view`.
- **Query Params**: `date_from`, `date_to`, `status`, `page`, `page_size`.
- **Responses**: `200 OK`: `PaginatedResponse[EventSummaryResponse]`

#### 2. `POST /api/v1/attendance/events`
- **Description**: Create a new event draft.
- **Capability**: `attendance.event.create` (`faculty`, `department_admin`, `org_admin`, `super_admin`).
- **Request Body**: `EventCreateRequest`
  - `title`: string
  - `event_date`: YYYY-MM-DD
  - `start_time`: HH:MM:SS
  - `end_time`: HH:MM:SS
  - `venue`: string
  - `description`: optional string
- **Responses**:
  - `201 Created`: `EventDetailResponse` (status initialized to `'draft'`)

#### 3. `GET /api/v1/attendance/events/{id}`
- **Description**: Get event details along with attendee list.
- **Capability**: Creator of event, or `dept_view` admin.
- **Responses**: `200 OK`: `EventDetailResponse`

#### 4. `PUT /api/v1/attendance/events/{id}`
- **Description**: Update event details (allowed only while status is `'draft'`).
- **Capability**: Creator of event (or super_admin).
- **Responses**:
  - `200 OK`: `EventDetailResponse`
  - `400 Bad Request`: Cannot edit an event once `'submitted'`.

#### 5. `PUT /api/v1/attendance/events/{id}/attendees`
- **Description**: Save draft attendee list (replace / upsert attendee rows).
- **Capability**: Creator of event.
- **Request Body**: `SaveAttendeesRequest`
  - `attendees`: array of `{ student_profile_id: int, current_attendance_percentage?: float }`
- **Responses**:
  - `200 OK`: `{ "message": "Attendees saved", "count": int }`

#### 6. `POST /api/v1/attendance/events/{id}/submit`
- **Description**: Finalize and submit event attendance. Transitions status from `'draft'` to `'submitted'`.
- **Capability**: Creator of event.
- **Rules**: Once submitted, attendees cannot be added/deleted by faculty.
- **Audit**: Writes audit log `SUBMIT_EVENT_ATTENDANCE`.
- **Responses**:
  - `200 OK`: `EventDetailResponse`

---

### 3.4 Attendance Correction Requests (`/requests`)

#### 1. `GET /api/v1/attendance/requests/my`
- **Description**: Returns all requests submitted by or belonging to the linked student.
- **Capability**: `attendance.student.own_requests` (`student` role).
- **Responses**: `200 OK`: `list[AttendanceRequestDetailResponse]`

#### 2. `POST /api/v1/attendance/requests`
- **Description**: Submit a new multi-item, multi-date attendance correction request.
- **Capability**: `attendance.student.own_requests` (or staff on behalf of student).
- **Request Body**: `AttendanceRequestCreateRequest`
  - `student_profile_id`: Optional (defaults to own linked profile for students; required if staff submits).
  - `current_attendance_percentage`: Optional float.
  - `items`: List of items, each containing:
    - `event_title`: string
    - `subject_id`: integer
    - `faculty_id`: integer
    - `start_time`: string (HH:MM)
    - `end_time`: string (HH:MM)
    - `reason`: string
    - `dates`: list of dates (YYYY-MM-DD)
- **Validation**:
  - Must have at least 1 item and each item must have at least 1 date.
  - Dates must not be in the future.
  - Snapshot fields are populated from current referenced master records.
- **Responses**:
  - `201 Created`: `AttendanceRequestDetailResponse` (status `'pending'`)

#### 3. `PUT /api/v1/attendance/requests/{id}`
- **Description**: Edit an existing request while still `'pending'`.
- **Capability**: Owner student.
- **Responses**:
  - `200 OK`: `AttendanceRequestDetailResponse`
  - `400 Bad Request`: If request status is not `'pending'`.

#### 4. `DELETE /api/v1/attendance/requests/{id}`
- **Description**: Cancel/delete a `'pending'` request.
- **Capability**: Owner student.
- **Responses**:
  - `204 No Content`
  - `400 Bad Request`: If request status is not `'pending'`.

#### 5. `GET /api/v1/attendance/requests/review-queue`
- **Description**: Pending and past review queue for administrators and approvers.
- **Capability**: `attendance.request.review` (`department_admin`, `org_admin`, `approver`, `super_admin`).
- **Query Params**: `status`, `department`, `page`, `page_size`.
- **Responses**: `200 OK`: `PaginatedResponse[AttendanceRequestDetailResponse]`

#### 6. `POST /api/v1/attendance/requests/{id}/review`
- **Description**: Review a request with item-by-item decisions and optimistic concurrency.
- **Capability**: `attendance.request.review` within scope.
- **Request Body**: `ReviewAttendanceRequestPayload`
  - `expected_version`: integer (for concurrency check)
  - `overall_status`: `'approved'` | `'rejected'` | `'partially_approved'`
  - `admin_comment`: string (required if rejected or partially approved)
  - `updated_percentage`: optional float (if admin adjusts student percentage)
  - `item_decisions`: optional list of `{ item_id: int, status: 'approved' | 'rejected', admin_note?: string }`
- **Responses**:
  - `200 OK`: `AttendanceRequestDetailResponse`
  - `409 Conflict`: If `version` does not match (concurrent review detected).

---

### 3.5 Reports, Analytics & Exports (`/reports`)

#### 1. `POST /api/v1/attendance/reports/query`
- **Description**: Server-side filtered query returning unified attendance and request rows.
- **Capability**: `attendance.report.view`.
- **Request Body**: `ReportFilterCriteriaPayload`
  - `semester`: integer or null
  - `section`: string or null
  - `department`: string or null
  - `faculty_name`: string or null
  - `subject_name`: string or null
  - `event_title`: string or null
  - `prn`: string or null
  - `student_name`: string or null
  - `date_from`, `date_to`: string or null
  - `request_status`: filter enum
  - `attendance_operator`: `'all'` | `'gte_75'` | `'lt_75'` | `'between'` | `'not_entered'` | `'entered'`
  - `custom_min`, `custom_max`: float
  - `sort_by`: string, `sort_order`: `'asc'` | `'desc'`
  - `page`: int, `page_size`: int
- **Responses**: `200 OK`: `ReportQueryResponse`

#### 2. `POST /api/v1/attendance/reports/export/excel`
- **Description**: Export filtered report to formatted `.xlsx` workbook (sanitized against formula injection).
- **Capability**: `attendance.export`.
- **Responses**: `200 OK` (binary stream `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).

#### 3. `GET /api/v1/attendance/events/{id}/export/pdf`
- **Description**: Generate formatted event attendance roster PDF.
- **Capability**: `attendance.export`.
- **Responses**: `200 OK` (binary stream `application/pdf`).

---

### 3.6 Audit Logs & Approver Scopes (`/audit-logs`, `/approver-scopes`)

#### 1. `GET /api/v1/attendance/audit-logs`
- **Description**: View immutable audit trail scoped to user permissions.
- **Capability**: `attendance.audit.view`.
- **Responses**: `200 OK`: `PaginatedResponse[AuditLogResponse]`

#### 2. `GET /api/v1/attendance/approver-scopes`
- **Description**: List assigned approver scopes.
- **Capability**: `org_admin`, `super_admin`.
- **Responses**: `200 OK`: `list[ApproverScopeResponse]`

#### 3. `POST /api/v1/attendance/approver-scopes`
- **Description**: Grant an approver review privileges over a department.
- **Capability**: `attendance.access.assign`.
- **Responses**: `201 Created`: `ApproverScopeResponse`

---

## 4. State Machines & Lifecycle Rules

### 4.1 Attendance Request State Machine

```
                   +-------------+
                   |  (Created)  |
                   +-------------+
                          |
                          v
                   +-------------+
                   |   PENDING   | <---------+ (Edited while pending)
                   +-------------+           |
                     |    |    |   ----------+
     All Items Apprv |    |    | All Items Rej
                     |    |    |
        +------------+    |    +-------------+
        |                 v                  |
        |          Mixed Decisions           |
        |                 |                  |
        v                 v                  v
+---------------+ +--------------------+ +---------------+
|   APPROVED    | | PARTIALLY_APPROVED | |   REJECTED    |
+---------------+ +--------------------+ +---------------+
        |                 |                  |
        +-----------------+------------------+
                          |
                          v
                 [Terminal States]
```

#### Derivation Rules
An admin cannot assign an arbitrary aggregate status that contradicts item decisions:
- If **every item** is marked `approved`, overall status **MUST** be `approved`.
- If **every item** is marked `rejected`, overall status **MUST** be `rejected`.
- If items contain a mixture of `approved` and `rejected`, overall status **MUST** be `partially_approved`.
- A request cannot transition out of `pending` if any item remains `pending`.
- Once in `approved`, `rejected`, or `partially_approved`, the request is **terminal** and cannot be edited or deleted by the student.

#### Optimistic Concurrency Protection
Every update to `att_requests` checks:
```sql
UPDATE att_requests
SET status = :new_status, version = version + 1, updated_at = NOW(), ...
WHERE id = :request_id AND version = :expected_version;
```
If 0 rows are affected, the API aborts with HTTP `409 Conflict` indicating another administrator has already reviewed or altered this request.

---

### 4.2 Event Attendance State Machine

```
+-------------+      Save Draft Attendees       +-------------+
|  (Created)  | -----------------------------> |    DRAFT    | <---+ (Draft update)
+-------------+                                +-------------+     |
                                                      |       -----+
                                        Submit Action |
                                                      v
                                               +-------------+
                                               |  SUBMITTED  |
                                               +-------------+
                                                      |
                                                      v
                                             [Locked to Faculty]
                                        (Admins can adjust % via Audit)
```

1. **Draft Phase**: The organiser can add, search, remove, or modify student attendees and save drafts repeatedly.
2. **Submission Phase**: When the organiser clicks "Submit Attendance", the event transitions to `'submitted'`.
3. **Immutability**: Once submitted, the attendee roster cannot be modified by the organiser. Any subsequent percentage override requires a department/org administrator and creates an audit entry.

---

## 5. Frontend Screen Map & Component Hierarchy

The attendance system is housed under the single dashboard layout at `/attendance/*`, using lazy loading to keep the main bundle lightweight.

### 5.1 Route Tree

```
/attendance
├── /attendance/dashboard               (Role-aware overview)
├── /attendance/student
│   ├── /attendance/student/requests    (My requests list)
│   └── /attendance/student/new-request (Multi-item correction form)
├── /attendance/organiser
│   ├── /attendance/organiser/events    (My created events list)
│   ├── /attendance/organiser/events/new (Event creation form)
│   └── /attendance/organiser/events/:id (Attendee entry & submission)
├── /attendance/admin
│   ├── /attendance/admin/review-queue  (Review pending requests)
│   ├── /attendance/admin/students      (Roster management & account linking)
│   ├── /attendance/admin/faculty       (Faculty master data)
│   ├── /attendance/admin/subjects      (Subject master data)
│   └── /attendance/admin/audit-logs    (Department/org audit view)
└── /attendance/reports                 (Multi-filter analytics & exports)
```

---

### 5.2 Role-to-Screen Access Matrix

| Screen | `student` | `faculty` | `approver` | `dept_admin` | `org_admin` | `super_admin` | `normal_user` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Attendance Overview** | Yes (Student view) | Yes (Faculty view) | Yes (Queue view) | Yes (Admin view) | Yes (Admin view) | Yes (Admin view) | No (Redirect) |
| **My Requests** | Yes | No | No | No | No | No | No |
| **Submit Request** | Yes | No | No | Yes (on-behalf) | Yes (on-behalf) | Yes (on-behalf) | No |
| **My Events List** | No | Yes | No | Yes | Yes | Yes | No |
| **Take Event Attendance**| No | Yes (own events) | No | Yes (dept events)| Yes (org events) | Yes (all) | No |
| **Review Queue** | No | No | Yes (scoped) | Yes (dept) | Yes (org) | Yes (all) | No |
| **Student Roster & Link**| No | No | No | Yes (dept) | Yes (org) | Yes (all) | No |
| **Faculty & Subjects** | No | View only | No | Manage (dept) | Manage (org) | Manage (all) | No |
| **Reports & Exports** | No | Own events | No | Dept wide | Org wide | Global | No |
| **Audit Log** | No | No | No | Dept audit | Org audit | Global audit | No |

---

### 5.3 UI Standards & Aesthetics

To maintain harmony with TemplateOS's existing design system:
1. **Color Palette**:
   - Primary: Indigo/Slate modern palette (`#4F46E5`, `#0F172A`)
   - Status Pending: Amber badge (`bg-amber-50 text-amber-700 border-amber-200`)
   - Status Approved: Emerald badge (`bg-emerald-50 text-emerald-700 border-emerald-200`)
   - Status Rejected: Rose badge (`bg-rose-50 text-rose-700 border-rose-200`)
   - Status Partial: Violet badge (`bg-violet-50 text-violet-700 border-violet-200`)
2. **Components**:
   - Built on existing Radix UI primitives (`@radix-ui/react-dialog`, `@radix-ui/react-select`, `@radix-ui/react-switch`).
   - Lucide icons (`CheckCircle2`, `Clock`, `AlertTriangle`, `FileSpreadsheet`, `Users`, `Calendar`, `ArrowRight`).
3. **Empty States**:
   - "No student profile linked" screen with step-by-step guidance.
   - Clean illustration, descriptive prompt, and action button for zero-state tables.

---

## 6. Implementation Checklist for Phase 3

- [ ] **3A**: Create SQLAlchemy models in `backend/app/models/attendance.py` matching Section 2.
- [ ] **3A**: Register models in `backend/app/models/__init__.py` and configure Alembic migration.
- [ ] **3A**: Implement `require_attendance_capability` dependency in `backend/app/api/deps.py`.
- [ ] **3A**: Write 46 automated security & capability tests in `backend/tests/attendance/test_permissions.py`.
- [ ] **3B**: Implement CRUD endpoints for students, faculty, and subjects.
- [ ] **3C**: Register sidebar link in `frontend/src/layouts/dashboard-layout.tsx` and configure lazy route bundle in `frontend/src/App.tsx`.
