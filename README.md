# Assignment Management System — Synthetic Workflow Dataset

A reproducible Python project that generates assignment lifecycle data, exports CSV/JSON, validates generated data, and loads all 13 normalized tables into PostgreSQL automatically.

## Requirements
- Python 3.10+
- PostgreSQL 14+ (pgAdmin 4 is optional and can be used to view the database)
- PostgreSQL database created in advance, e.g. `assignment_management`

## Windows PowerShell setup
Run these commands from the project root (the folder containing `src`, `sql`, and `requirements.txt`):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again.

## 1. Generate the full synthetic dataset

```powershell
python -m src.generator
```

The default configuration uses seed `20261022` and creates the requested baseline scale (100 courses, 10,000 learners, 1,000 assignments and 30,000 initial submissions/grades). Resubmissions add additional submission records. Output is written to `data/generated/`. The generator prints row counts and validation results.

For a smaller test run:

```powershell
python -m src.generator --courses 10 --learners 100 --assignments 20 --submissions 300
```

## 2. Create a PostgreSQL database

In pgAdmin 4, right-click **Databases → Create → Database**, name it `assignment_management`, and save. The schema and loader below can also be run against an existing database.

## 3. Automatically create schema and load every CSV

The loader does not require `psql` or manual per-table imports. It uses the installed `psycopg` package and PostgreSQL `COPY` for efficient bulk loading. It creates tables from `sql/schema.sql`, loads all 13 CSV files in foreign-key dependency order, and checks that database row counts match the CSV files. All imports run in one transaction; a failed import is rolled back.

Run:

```powershell
python -m src.db_loader --dbname assignment_management --user postgres --create-schema
```

Enter your PostgreSQL password when prompted. The password is not displayed or saved.

If your PostgreSQL server uses a different host, port, database, or username:

```powershell
python -m src.db_loader --host localhost --port 5432 --dbname assignment_management --user postgres --create-schema
```

Alternatively, set a connection URL in the environment and run the loader:

```powershell
$env:DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/assignment_management"
python -m src.db_loader --create-schema
```

### Re-loading after regenerating data

If the tables already contain data, a second load will correctly stop on duplicate primary keys rather than silently overwrite existing data. To explicitly replace the contents of all 13 project tables and load the current CSVs, use:

```powershell
python -m src.db_loader --dbname assignment_management --user postgres --create-schema --replace
```

**Warning:** `--replace` deletes the existing rows in these project tables before loading. Use it only when you intend to replace the dataset.

## 4. Verify in pgAdmin

Open pgAdmin → `assignment_management` → **Tools → Query Tool**, then open `sql/verify.sql` and execute it. It displays row counts for all 13 tables and three referential-integrity checks (each expected to be zero).

You can also run a simple query:

```sql
SELECT COUNT(*) FROM learner;
SELECT COUNT(*) FROM assignment;
SELECT COUNT(*) FROM submission;
SELECT COUNT(*) FROM grade;
```

## Tables loaded

`course`, `learner`, `enrollment`, `assignment`, `rubric`, `rubric_criterion`, `submission`, `submission_artifact`, `grade`, `feedback`, `resubmission`, `appeal`, and `workflow_event`.

`ground_truth.csv` is deliberately kept outside the operational schema because it contains evaluation labels. The loader reports its row count but does not load it into the application tables.

## Reproducibility and evaluation

- Default seed: `20261022`.
- Re-running the generator with the same seed and parameters reproduces the generated records (the run timestamp in the manifest changes).
- Four labelled anomaly categories are included for evaluation; see `ground_truth.csv` and `DATA_DICTIONARY.md`.
- Keep ground-truth labels out of model features to avoid data leakage.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Project structure

- `src/generator.py` — deterministic generator, exports, validation, optional SQLite inspection loader.
- `src/db_loader.py` — complete transactional PostgreSQL schema + CSV loader.
- `sql/schema.sql` — normalized PostgreSQL schema and constraints.
- `sql/verify.sql` — database row-count and relationship checks.
- `DATA_DICTIONARY.md` — fields, constraints and cardinalities.
- `PROMPT_HISTORY.md` — AI-use disclosure template.
- `data/generated/` — generated CSV/JSON examples; regenerate to create the full dataset.

## Scope note

This repository implements synthetic workflow data generation, relational storage, loading, and validation. It is not a deployed multi-user application: authenticated APIs, role-based authorization, real object storage, and production audit services would be separate implementation work. All records and artifact URIs are synthetic.
