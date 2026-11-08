"""Deterministic synthetic assignment workflow data generator."""
from __future__ import annotations
import argparse, csv, json, random, hashlib, sqlite3, os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SEED = 20261022
TABLES = [
    "course", "learner", "enrollment", "assignment", "rubric",
    "rubric_criterion", "submission", "submission_artifact", "grade",
    "feedback", "resubmission", "appeal", "workflow_event"
]

def iso(dt): return dt.isoformat(timespec="seconds")
def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        path.write_text("", encoding="utf-8"); return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

def build_dataset(seed=SEED, courses_n=100, learners_n=10000, assignments_n=1000,
                  submissions_n=30000, output_dir="data/generated"):
    rng = random.Random(seed)
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    tz = ZoneInfo("Asia/Kolkata")
    now = datetime(2026, 11, 1, 12, 0, tzinfo=tz)

    courses, learners, enrollments = [], [], []
    for i in range(1, courses_n + 1):
        courses.append({"course_id": f"CRS-2026-{i:04d}", "course_code": f"CS{i:04d}",
                        "course_name": f"Course {i:04d}", "department": rng.choice(["CSE","ECE","IT","EEE"]),
                        "status": "active", "created_at": iso(now - timedelta(days=rng.randint(30,500)))})
    for i in range(1, learners_n + 1):
        learners.append({"learner_id": f"LRN-2026-{i:06d}", "full_name": f"Learner {i:06d}",
                         "email": f"learner{i:06d}@example.edu", "status": "active",
                         "created_at": iso(now - timedelta(days=rng.randint(10,700)))})
    course_ids = [x["course_id"] for x in courses]
    learner_ids = [x["learner_id"] for x in learners]
    enrollment_pairs = set()
    for learner in learners:
        for cid in rng.sample(course_ids, k=min(rng.randint(1,3), len(course_ids))):
            enrollment_pairs.add((learner["learner_id"], cid))
    enrollments = [{"enrollment_id": f"ENR-{i:07d}", "learner_id": lid, "course_id": cid,
                    "enrolled_at": iso(now - timedelta(days=rng.randint(1,400))),
                    "status": "active"} for i,(lid,cid) in enumerate(sorted(enrollment_pairs),1)]

    assignments, rubrics, criteria = [], [], []
    assignment_course = {}
    for i in range(1, assignments_n + 1):
        aid = f"ASN-2026-{i:06d}"; cid = rng.choice(course_ids)
        published = now - timedelta(days=rng.randint(1,150))
        due = published + timedelta(days=rng.randint(7,30))
        max_score = 20
        assignments.append({"assignment_id": aid, "course_id": cid, "title": f"Assignment {i:04d}",
            "description": f"Synthetic assignment brief {i:04d}", "published_at": iso(published),
            "due_at": iso(due), "timezone": "Asia/Kolkata", "max_score": max_score,
            "late_policy": "5_percent_per_day_capped_25_percent", "resubmission_allowed": "true",
            "resubmission_deadline_days": 7, "status": "published"})
        assignment_course[aid] = cid
        rid = f"RUB-{aid}-01"
        rubrics.append({"rubric_id": rid, "assignment_id": aid, "version": 1,
                        "max_score": max_score, "effective_from": iso(published), "status": "active"})
        for j, (name, weight) in enumerate([("Understanding",5),("Method",5),("Accuracy",5),("Presentation",5)],1):
            criteria.append({"criterion_id": f"{rid}-C{j:02d}", "rubric_id": rid,
                "criterion_name": name, "description": f"Assessment of {name.lower()}",
                "max_points": weight, "weight": weight, "required": "true"})

    # Select valid enrolled learners for baseline submissions; each assignment receives 30.
    enroll_by_course = {}
    for e in enrollments: enroll_by_course.setdefault(e["course_id"], []).append(e["learner_id"])
    submissions, artifacts, grades, feedbacks, resubs, appeals, events = [], [], [], [], [], [], []
    used_pairs = set()
    for i in range(1, submissions_n + 1):
        a = assignments[(i-1) % len(assignments)]
        eligible = enroll_by_course.get(a["course_id"], learner_ids)
        lid = rng.choice(eligible)
        # Ensure unique learner/assignment/version combinations.
        tries = 0
        while (a["assignment_id"], lid) in used_pairs and tries < 20:
            lid = rng.choice(eligible); tries += 1
        used_pairs.add((a["assignment_id"], lid))
        sid = f"SUB-{a['assignment_id']}-{lid}-01"
        due = datetime.fromisoformat(a["due_at"])
        submitted = due + timedelta(hours=rng.randint(-120,120))
        missing_file = (i % 97 == 0)
        status = "submitted"
        submissions.append({"submission_id": sid, "assignment_id": a["assignment_id"], "learner_id": lid,
            "version": 1, "submitted_at": iso(submitted), "status": status,
            "is_late": str(submitted > due).lower(), "issue_type": "missing_file" if missing_file else "",
            "ground_truth": "missing_file" if missing_file else ""})
        if not missing_file:
            artifacts.append({"artifact_id": f"ART-{i:07d}", "submission_id": sid,
                "file_name": f"submission_{i:07d}.pdf", "mime_type": "application/pdf",
                "size_bytes": rng.randint(12000,900000), "checksum": hashlib.sha256(f"{seed}:{sid}".encode()).hexdigest(),
                "uploaded_at": iso(submitted), "storage_uri": f"synthetic://submissions/{sid}/submission.pdf"})
        raw_scores = [rng.randint(2,5) for _ in range(4)]
        raw_total = sum(raw_scores)
        penalty_pct = min(25, max(0, ((submitted.date()-due.date()).days) * 5))
        penalty = round(raw_total * penalty_pct / 100, 2)
        final_score = round(max(0, raw_total-penalty),2)
        gid = f"GRD-{sid}"
        grades.append({"grade_id": gid, "submission_id": sid, "rubric_id": f"RUB-{a['assignment_id']}-01",
            "raw_score": raw_total, "late_penalty_pct": penalty_pct, "late_penalty_points": penalty,
            "final_score": final_score, "max_score": 20, "graded_at": iso(submitted+timedelta(hours=rng.randint(1,72))),
            "grader_id": f"INS-{rng.randint(1,50):04d}", "grade_version": 1, "issue_type": "", "ground_truth": ""})
        for j, pts in enumerate(raw_scores,1):
            feedbacks.append({"feedback_id": f"FDB-{i:07d}-{j:02d}", "grade_id": gid,
                "criterion_id": f"RUB-{a['assignment_id']}-01-C{j:02d}", "points_awarded": pts,
                "comment": ["Good understanding","Method is mostly correct","Check calculation details","Clear presentation"][j-1],
                "created_at": iso(submitted+timedelta(hours=rng.randint(2,80)))})
        events.append({"event_id": f"EVT-{i:07d}-01", "entity_type": "submission", "entity_id": sid,
            "event_type": "submitted", "from_state": "draft", "to_state": "submitted",
            "event_at": iso(submitted), "actor_id": lid, "metadata_json": "{}"})
        # Some resubmissions within policy; original rows remain.
        if i % 13 == 0:
            rsid = f"SUB-{a['assignment_id']}-{lid}-02"
            resub_at = submitted + timedelta(days=rng.randint(1,5))
            submissions.append({"submission_id": rsid, "assignment_id": a["assignment_id"], "learner_id": lid,
                "version": 2, "submitted_at": iso(resub_at), "status": "resubmitted",
                "is_late": str(resub_at > due).lower(), "issue_type": "", "ground_truth": ""})
            artifacts.append({"artifact_id": f"ART-R{i:07d}", "submission_id": rsid,
                "file_name": f"resubmission_{i:07d}.pdf", "mime_type": "application/pdf",
                "size_bytes": rng.randint(12000,900000), "checksum": hashlib.sha256(f"{seed}:{rsid}".encode()).hexdigest(),
                "uploaded_at": iso(resub_at), "storage_uri": f"synthetic://submissions/{rsid}/submission.pdf"})
            resubs.append({"resubmission_id": f"RSB-{i:07d}", "original_submission_id": sid,
                "new_submission_id": rsid, "requested_at": iso(resub_at-timedelta(hours=1)),
                "decision": "approved", "policy_window_days": 7, "reason": "Learner requested improvement"})
            events.append({"event_id": f"EVT-{i:07d}-02", "entity_type": "submission", "entity_id": rsid,
                "event_type": "resubmitted", "from_state": "submitted", "to_state": "resubmitted",
                "event_at": iso(resub_at), "actor_id": lid, "metadata_json": "{}"})
        if i % 29 == 0:
            apid = f"APP-2026-{len(appeals)+1:06d}"
            decision = rng.choice(["upheld","partially_upheld","rejected"])
            appeals.append({"appeal_id": apid, "submission_id": sid, "learner_id": lid,
                "submitted_at": iso(submitted+timedelta(days=2)), "reason": "Request for rubric review",
                "decision": decision, "decided_at": iso(submitted+timedelta(days=4)),
                "decision_notes": "Reviewed against published rubric", "grade_before": final_score,
                "grade_after": round(min(20,final_score+(1 if decision=="partially_upheld" else 0)),2),
                "audit_event_id": f"EVT-APP-{len(appeals)+1:06d}"})
            events.append({"event_id": f"EVT-APP-{len(appeals):06d}", "entity_type": "appeal", "entity_id": apid,
                "event_type": "appeal_decided", "from_state": "open", "to_state": decision,
                "event_at": iso(submitted+timedelta(days=4)), "actor_id": "INS-0001", "metadata_json": "{}"})

    # Four intentional labelled anomalies; do not silently damage other records.
    gt = []
    # 1. Submission from an unenrolled learner.
    if submissions:
        s = submissions[0]; s["learner_id"] = learner_ids[-1]; s["issue_type"] = "unenrolled_learner"; s["ground_truth"] = "invalid_enrollment"
        gt.append({"record_type":"submission","record_id":s["submission_id"],"issue_type":"unenrolled_learner",
                   "expected_decision":"reject_submission_or_flag_enrollment","severity":"high"})
    # 2. Grade exceeds rubric maximum.
    if grades:
        g = grades[1 if len(grades)>1 else 0]; g["raw_score"] = 25; g["final_score"] = 25
        g["issue_type"]="grade_exceeds_rubric_max"; g["ground_truth"]="invalid_score"
        gt.append({"record_type":"grade","record_id":g["grade_id"],"issue_type":"grade_exceeds_rubric_max",
                   "expected_decision":"block_grade_release","severity":"high"})
    # 3. Duplicate late penalty event.
    if grades:
        g = grades[2 if len(grades)>2 else 0]
        g["late_penalty_points"] = round(g["late_penalty_points"]*2,2)
        g["issue_type"]="late_penalty_applied_twice"; g["ground_truth"]="duplicate_penalty"
        gt.append({"record_type":"grade","record_id":g["grade_id"],"issue_type":"late_penalty_applied_twice",
                   "expected_decision":"apply_penalty_once_and_reconcile","severity":"medium"})
    # 4. Appeal changes grade without corresponding audit event.
    if appeals:
        ap = appeals[0]; ap["grade_after"] = round(min(20, ap["grade_before"]+2),2)
        ap["audit_event_id"] = ""; ap["decision_notes"] = "Intentional anomaly: missing audit history"
        gt.append({"record_type":"appeal","record_id":ap["appeal_id"],"issue_type":"grade_change_without_audit",
                   "expected_decision":"quarantine_change_until_audit_event_exists","severity":"high"})

    data = {"course":courses,"learner":learners,"enrollment":enrollments,"assignment":assignments,
        "rubric":rubrics,"rubric_criterion":criteria,"submission":submissions,"submission_artifact":artifacts,
        "grade":grades,"feedback":feedbacks,"resubmission":resubs,"appeal":appeals,"workflow_event":events}
    for name, rows in data.items():
        write_csv(out/f"{name}.csv", rows)
        with (out/f"{name}.json").open("w",encoding="utf-8") as f: json.dump(rows,f,indent=2)
    write_csv(out/"ground_truth.csv", gt)
    (out/"ground_truth.json").write_text(json.dumps(gt,indent=2),encoding="utf-8")
    return data, gt

def validate(data, gt):
    checks=[]
    def add(name, passed, detail): checks.append({"check":name,"passed":bool(passed),"detail":detail})
    for table, key in [("course","course_id"),("learner","learner_id"),("assignment","assignment_id"),
                       ("submission","submission_id"),("grade","grade_id")]:
        vals=[r[key] for r in data[table]]
        add(f"{table}_primary_key_unique",len(vals)==len(set(vals)),f"{len(vals)} rows; {len(vals)-len(set(vals))} duplicates")
    courses={r["course_id"] for r in data["course"]}
    learners={r["learner_id"] for r in data["learner"]}
    assignments={r["assignment_id"] for r in data["assignment"]}
    submissions={r["submission_id"] for r in data["submission"]}
    add("assignment_course_fk",all(r["course_id"] in courses for r in data["assignment"]),"All assignments reference courses")
    add("submission_assignment_fk",all(r["assignment_id"] in assignments for r in data["submission"]),"All submissions reference assignments")
    add("submission_learner_fk",all(r["learner_id"] in learners for r in data["submission"]),"All submissions reference learners")
    add("artifact_submission_fk",all(r["submission_id"] in submissions for r in data["submission_artifact"]),"All artifacts reference submissions")
    # Anomaly is intentionally present; exclude its labelled record from baseline enrollment integrity.
    enrolled={(r["learner_id"],r["course_id"]) for r in data["enrollment"]}
    asn={r["assignment_id"]:r["course_id"] for r in data["assignment"]}
    bad=[r for r in data["submission"] if (r["learner_id"],asn[r["assignment_id"]]) not in enrolled]
    labelled={x["record_id"] for x in gt if x["issue_type"]=="unenrolled_learner"}
    add("enrollment_integrity_except_labelled_anomaly",all(r["submission_id"] in labelled for r in bad),
        f"{len(bad)} enrollment exceptions; {len(labelled)} intentionally labelled")
    critmax={}
    for c in data["rubric_criterion"]: critmax[c["rubric_id"]]=critmax.get(c["rubric_id"],0)+int(c["max_points"])
    grade_anoms={x["record_id"] for x in gt if x["issue_type"]=="grade_exceeds_rubric_max"}
    over=[g for g in data["grade"] if float(g["raw_score"])>float(g["max_score"])]
    add("grade_max_except_labelled_anomaly",all(g["grade_id"] in grade_anoms for g in over),
        f"{len(over)} over-maximum grades; {len(grade_anoms)} intentionally labelled")
    add("ground_truth_separate",all("ground_truth" not in r for r in data["course"]+data["learner"]+data["assignment"]),
        "Ground truth is exported separately; row issue labels are retained for anomaly tracing")
    return checks

def write_manifest(out, data, checks, seed):
    manifest={"seed":seed,"generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "tables":{k:{"rows":len(v),"csv":f"{k}.csv","json":f"{k}.json"} for k,v in data.items()},
      "validation":{"passed":sum(x["passed"] for x in checks),"total":len(checks)},
      "provenance":"Fully synthetic records; no external personal data or external datasets."}
    (out/"source_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    (out/"validation_summary.json").write_text(json.dumps(checks,indent=2),encoding="utf-8")
    with (out/"validation_summary.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["check","passed","detail"]);w.writeheader();w.writerows(checks)

def load_sqlite(data, db_path):
    db_path=Path(db_path); db_path.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(db_path); con.execute("PRAGMA foreign_keys=ON")
    # Load as flexible JSON payload tables; canonical relational schema is in sql/schema.sql.
    for name, rows in data.items():
        con.execute(f'DROP TABLE IF EXISTS "{name}"')
        con.execute(f'CREATE TABLE "{name}" (row_id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        con.executemany(f'INSERT INTO "{name}"(payload) VALUES (?)',[(json.dumps(r),) for r in rows])
    con.commit(); con.close()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--seed",type=int,default=SEED)
    p.add_argument("--courses",type=int,default=100)
    p.add_argument("--learners",type=int,default=10000)
    p.add_argument("--assignments",type=int,default=1000)
    p.add_argument("--submissions",type=int,default=30000)
    p.add_argument("--output",default="data/generated")
    p.add_argument("--load-sqlite",action="store_true")
    args=p.parse_args()
    data,gt=build_dataset(args.seed,args.courses,args.learners,args.assignments,args.submissions,args.output)
    checks=validate(data,gt); out=Path(args.output); write_manifest(out,data,checks,args.seed)
    if args.load_sqlite: load_sqlite(data,"data/assignment_workflow.db")
    print("Generation complete")
    print(f"Output: {out.resolve()}")
    print(f"Rows: " + ", ".join(f"{k}={len(v)}" for k,v in data.items()))
    print(f"Validation: {sum(c['passed'] for c in checks)}/{len(checks)} checks passed")
    if not all(c["passed"] for c in checks): raise SystemExit(2)
if __name__=="__main__": main()
