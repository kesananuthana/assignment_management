-- PostgreSQL relational schema. Run with: psql "$DATABASE_URL" -f sql/schema.sql
CREATE TABLE IF NOT EXISTS course (
 course_id varchar(32) PRIMARY KEY, course_code varchar(20) UNIQUE NOT NULL,
 course_name text NOT NULL, department varchar(20) NOT NULL, status varchar(20) NOT NULL,
 created_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS learner (
 learner_id varchar(32) PRIMARY KEY, full_name text NOT NULL,
 email text UNIQUE NOT NULL, status varchar(20) NOT NULL, created_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS enrollment (
 enrollment_id varchar(32) PRIMARY KEY, learner_id varchar(32) NOT NULL REFERENCES learner,
 course_id varchar(32) NOT NULL REFERENCES course, enrolled_at timestamptz NOT NULL,
 status varchar(20) NOT NULL, UNIQUE(learner_id,course_id)
);
CREATE TABLE IF NOT EXISTS assignment (
 assignment_id varchar(32) PRIMARY KEY, course_id varchar(32) NOT NULL REFERENCES course,
 title text NOT NULL, description text, published_at timestamptz NOT NULL, due_at timestamptz NOT NULL,
 timezone varchar(64) NOT NULL, max_score numeric(8,2) NOT NULL CHECK(max_score>0),
 late_policy text NOT NULL, resubmission_allowed boolean NOT NULL,
 resubmission_deadline_days integer NOT NULL CHECK(resubmission_deadline_days>=0),
 status varchar(20) NOT NULL, CHECK(due_at>published_at)
);
CREATE TABLE IF NOT EXISTS rubric (
 rubric_id text PRIMARY KEY, assignment_id varchar(32) NOT NULL REFERENCES assignment,
 version integer NOT NULL, max_score numeric(8,2) NOT NULL, effective_from timestamptz NOT NULL,
 status varchar(20) NOT NULL, UNIQUE(assignment_id,version)
);
CREATE TABLE IF NOT EXISTS rubric_criterion (
 criterion_id text PRIMARY KEY, rubric_id text NOT NULL REFERENCES rubric,
 criterion_name text NOT NULL, description text, max_points numeric(8,2) NOT NULL CHECK(max_points>=0),
 weight numeric(8,2) NOT NULL, required boolean NOT NULL
);
CREATE TABLE IF NOT EXISTS submission (
 submission_id text PRIMARY KEY, assignment_id varchar(32) NOT NULL REFERENCES assignment,
 learner_id varchar(32) NOT NULL REFERENCES learner, version integer NOT NULL,
 submitted_at timestamptz NOT NULL, status varchar(24) NOT NULL, is_late boolean NOT NULL,
 issue_type text, ground_truth text, UNIQUE(assignment_id,learner_id,version)
);
CREATE TABLE IF NOT EXISTS submission_artifact (
 artifact_id text PRIMARY KEY, submission_id text NOT NULL REFERENCES submission,
 file_name text NOT NULL, mime_type text NOT NULL, size_bytes bigint NOT NULL CHECK(size_bytes>0),
 checksum text NOT NULL, uploaded_at timestamptz NOT NULL, storage_uri text NOT NULL
);
CREATE TABLE IF NOT EXISTS grade (
 grade_id text PRIMARY KEY, submission_id text NOT NULL REFERENCES submission,
 rubric_id text NOT NULL REFERENCES rubric, raw_score numeric(8,2) NOT NULL,
 late_penalty_pct numeric(5,2) NOT NULL, late_penalty_points numeric(8,2) NOT NULL,
 final_score numeric(8,2) NOT NULL, max_score numeric(8,2) NOT NULL,
 graded_at timestamptz NOT NULL, grader_id text NOT NULL, grade_version integer NOT NULL,
 issue_type text, ground_truth text
);
CREATE TABLE IF NOT EXISTS feedback (
 feedback_id text PRIMARY KEY, grade_id text NOT NULL REFERENCES grade,
 criterion_id text NOT NULL REFERENCES rubric_criterion, points_awarded numeric(8,2) NOT NULL,
 comment text NOT NULL, created_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS resubmission (
 resubmission_id text PRIMARY KEY, original_submission_id text NOT NULL REFERENCES submission,
 new_submission_id text NOT NULL REFERENCES submission, requested_at timestamptz NOT NULL,
 decision text NOT NULL, policy_window_days integer NOT NULL, reason text NOT NULL
);
CREATE TABLE IF NOT EXISTS appeal (
 appeal_id varchar(32) PRIMARY KEY, submission_id text NOT NULL REFERENCES submission,
 learner_id varchar(32) NOT NULL REFERENCES learner, submitted_at timestamptz NOT NULL,
 reason text NOT NULL, decision text NOT NULL, decided_at timestamptz,
 decision_notes text, grade_before numeric(8,2), grade_after numeric(8,2), audit_event_id text
);
CREATE TABLE IF NOT EXISTS workflow_event (
 event_id text PRIMARY KEY, entity_type text NOT NULL, entity_id text NOT NULL,
 event_type text NOT NULL, from_state text, to_state text, event_at timestamptz NOT NULL,
 actor_id text NOT NULL, metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_submission_assignment ON submission(assignment_id);
CREATE INDEX IF NOT EXISTS idx_submission_learner ON submission(learner_id);
CREATE INDEX IF NOT EXISTS idx_grade_submission ON grade(submission_id);
CREATE INDEX IF NOT EXISTS idx_appeal_submission ON appeal(submission_id);
