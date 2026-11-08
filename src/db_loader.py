"""Load generated CSV files into the normalized PostgreSQL schema.

Usage:
  python -m src.db_loader --dbname assignment_management --user postgres --create-schema
  python -m src.db_loader --database-url postgresql://postgres:password@localhost:5432/assignment_management --replace

The loader uses psycopg 3 and PostgreSQL COPY for efficient bulk loading. All
loads happen in one transaction: a failed table import rolls the whole load back.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import os
from pathlib import Path
from typing import Iterable

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "generated"
SCHEMA_FILE = ROOT / "sql" / "schema.sql"

# Parent tables must be loaded before their dependent tables.
LOAD_ORDER = [
    "course",
    "learner",
    "enrollment",
    "assignment",
    "rubric",
    "rubric_criterion",
    "submission",
    "submission_artifact",
    "grade",
    "feedback",
    "resubmission",
    "appeal",
    "workflow_event",
]


def csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV is empty: {path}") from exc


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(sum(1 for _ in csv.reader(handle)) - 1, 0)


def load_one_table(cur: psycopg.Cursor, table: str, csv_path: Path) -> int:
    if not csv_path.is_file():
        raise FileNotFoundError(f"Missing generated CSV: {csv_path}")

    headers = csv_headers(csv_path)
    db_columns = cur.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = %s
           ORDER BY ordinal_position""",
        (table,),
    ).fetchall()
    expected = [row[0] for row in db_columns]
    if headers != expected:
        raise ValueError(
            f"Column mismatch for {table}.\nCSV: {headers}\nDB:  {expected}\n"
            "The CSV and schema.sql must come from the same project version."
        )

    copied = 0
    copy_stmt = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, headers)),
    )
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        with cur.copy(copy_stmt) as copy:
            for row in reader:
                # write_row performs type adaptation; empty CSV cells become SQL NULL.
                copy.write_row(tuple(row[name] if row[name] != "" else None for name in headers))
                copied += 1
    return copied


def build_connection(args: argparse.Namespace) -> psycopg.Connection:
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if database_url:
        return psycopg.connect(database_url)

    password = args.password
    if password is None:
        password = getpass.getpass(f"Password for PostgreSQL user '{args.user}': ")
    return psycopg.connect(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=password,
    )


def run_load(args: argparse.Namespace) -> dict[str, int]:
    data_dir = Path(args.data_dir).expanduser().resolve()
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Generated data directory not found: {data_dir}")

    with build_connection(args) as conn:
        with conn.cursor() as cur:
            if args.create_schema:
                schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
                cur.execute(schema_sql)

            if args.replace:
                # Explicit opt-in: this removes existing rows from these project tables.
                cur.execute(
                    sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                        sql.SQL(", ").join(map(sql.Identifier, reversed(LOAD_ORDER)))
                    )
                )

            counts: dict[str, int] = {}
            for table in LOAD_ORDER:
                counts[table] = load_one_table(cur, table, data_dir / f"{table}.csv")

            # Ground-truth labels are evaluation metadata, intentionally not part of
            # the operational relational schema. Report its row count separately.
            ground_truth_path = data_dir / "ground_truth.csv"
            if ground_truth_path.exists():
                counts["ground_truth (evaluation file; not loaded)"] = count_csv_rows(ground_truth_path)

            # Validate committed database counts against the imported CSV row counts.
            for table in LOAD_ORDER:
                actual = cur.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
                ).fetchone()[0]
                if actual != counts[table]:
                    raise RuntimeError(
                        f"Row-count verification failed for {table}: "
                        f"CSV={counts[table]}, database={actual}"
                    )

        # Connection context commits only after every table and check succeeds.
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load generated assignment workflow CSVs into PostgreSQL.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Folder containing generated CSV files")
    parser.add_argument("--database-url", help="PostgreSQL connection URL; alternatively set DATABASE_URL")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--dbname", default="assignment_management")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--password", help="Password (omit to enter it securely at the prompt)")
    parser.add_argument("--create-schema", action="store_true", help="Apply sql/schema.sql before loading")
    parser.add_argument("--replace", action="store_true", help="TRUNCATE project tables before loading; destructive")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        counts = run_load(args)
    except Exception as exc:
        raise SystemExit(f"\nLOAD FAILED — no partial import was committed.\n{type(exc).__name__}: {exc}") from exc

    print("\nPostgreSQL load completed successfully.")
    print(f"Database: {args.dbname if not args.database_url and not os.getenv('DATABASE_URL') else 'from connection URL'}")
    print("Rows loaded and verified:")
    for table, count in counts.items():
        print(f"  {table}: {count:,}")
    print(f"\nTables loaded: {len(LOAD_ORDER)}")
    print("All database row counts match the generated CSV files.")


if __name__ == "__main__":
    main()
