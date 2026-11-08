# Data dictionary

All timestamps are ISO-8601 with an explicit Asia/Kolkata offset. IDs are immutable strings. Synthetic emails use `example.edu`; artifacts use synthetic URIs and are not real files.

| Entity | Primary key | Main foreign keys | Important fields / validation |
|---|---|---|---|
| Course | course_id | — | course_code unique; status active/inactive |
| Learner | learner_id | — | email unique; status active/inactive |
| Enrollment | enrollment_id | learner_id, course_id | unique learner/course; enrolled_at timestamp; active/inactive |
| Assignment | assignment_id | course_id | published_at < due_at; max_score > 0; timezone-aware; status draft/published/closed |
| Rubric | rubric_id | assignment_id | unique assignment/version; max_score reconciles to criteria |
| RubricCriterion | criterion_id | rubric_id | max_points >= 0; weight >= 0; criterion name required |
| Submission | submission_id | assignment_id, learner_id | version >= 1; submitted_at timestamp; status submitted/resubmitted; is_late derived |
| SubmissionArtifact | artifact_id | submission_id | size_bytes > 0; checksum SHA-256; mime_type required |
| Grade | grade_id | submission_id, rubric_id | raw_score, penalty, final_score and max_score; normal score must be within rubric max |
| Feedback | feedback_id | grade_id, criterion_id | points_awarded within criterion maximum; comment required |
| Resubmission | resubmission_id | original_submission_id, new_submission_id | decision approved/rejected; requested_at and policy window |
| Appeal | appeal_id | submission_id, learner_id | decision upheld/partially_upheld/rejected; grade_before/after; audit_event_id required for real grade change |
| WorkflowEvent | event_id | polymorphic entity reference | append-only state transition; actor, timestamp and JSON metadata |

## Cardinality

- Course 1:N Assignment; Course N:M Learner through Enrollment.
- Assignment 1:1 or 1:N Rubric versions; Rubric 1:N RubricCriterion.
- Assignment 1:N Submission; Learner 1:N Submission.
- Submission 1:N SubmissionArtifact; Submission 1:N Grade versions.
- Grade 1:N Feedback; RubricCriterion 1:N Feedback.
- Submission 1:N Appeal; original Submission 1:N Resubmission records.
- Any workflow entity 1:N WorkflowEvent (polymorphic event history).

## Derived rules

- `is_late = submitted_at > due_at` using timezone-aware datetimes.
- Late penalty = min(25%, late_days × 5%); points = raw_score × penalty percentage.
- Final score = max(0, raw_score − penalty points).
- Baseline rubric has four criteria worth 5 points each (20 total).
- Missing artifact is a valid flagged exception, not a broken foreign key.
- Four intentional anomalies are listed in `ground_truth.csv/json`; do not use ground-truth columns as model input.
