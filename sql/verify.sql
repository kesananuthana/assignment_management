-- Run in pgAdmin Query Tool after loading the generated CSV files.
SELECT 'course' AS table_name, COUNT(*) AS row_count FROM course
UNION ALL SELECT 'learner', COUNT(*) FROM learner
UNION ALL SELECT 'enrollment', COUNT(*) FROM enrollment
UNION ALL SELECT 'assignment', COUNT(*) FROM assignment
UNION ALL SELECT 'rubric', COUNT(*) FROM rubric
UNION ALL SELECT 'rubric_criterion', COUNT(*) FROM rubric_criterion
UNION ALL SELECT 'submission', COUNT(*) FROM submission
UNION ALL SELECT 'submission_artifact', COUNT(*) FROM submission_artifact
UNION ALL SELECT 'grade', COUNT(*) FROM grade
UNION ALL SELECT 'feedback', COUNT(*) FROM feedback
UNION ALL SELECT 'resubmission', COUNT(*) FROM resubmission
UNION ALL SELECT 'appeal', COUNT(*) FROM appeal
UNION ALL SELECT 'workflow_event', COUNT(*) FROM workflow_event
ORDER BY table_name;

-- Referential-integrity spot checks. These should all return zero.
SELECT 'submissions without assignment' AS check_name, COUNT(*) AS failures
FROM submission s LEFT JOIN assignment a USING (assignment_id) WHERE a.assignment_id IS NULL
UNION ALL
SELECT 'grades without submission', COUNT(*)
FROM grade g LEFT JOIN submission s USING (submission_id) WHERE s.submission_id IS NULL
UNION ALL
SELECT 'feedback without grade', COUNT(*)
FROM feedback f LEFT JOIN grade g USING (grade_id) WHERE g.grade_id IS NULL;
