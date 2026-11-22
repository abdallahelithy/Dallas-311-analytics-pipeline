"""Dallas 311: first-stage API -> validation -> SQLite -> aggregated reports.

This is a starter pipeline, not a production-certified complete data warehouse.
Requires Python 3.10+; uses only the standard library.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://www.dallasopendata.com/resource/d7e7-envw.json"
# Intentionally omit address and precise coordinates from source and storage.
COLUMNS = (
    "unique_key", "service_request_number", "created_date", "update_date",
    "closed_date", "status", "department", "service_request_type",
    "city_council_district", "priority", "method_received_description",
)

DDL = """
CREATE TABLE IF NOT EXISTS service_requests (
    unique_key TEXT PRIMARY KEY,
    service_request_number TEXT,
    created_date TEXT NOT NULL,
    update_date TEXT,
    closed_date TEXT,
    status TEXT,
    department TEXT,
    service_request_type TEXT,
    city_council_district TEXT,
    priority TEXT,
    method_received_description TEXT
);
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_utc TEXT NOT NULL,
    mode TEXT NOT NULL,
    days INTEGER NOT NULL,
    rows_fetched INTEGER NOT NULL,
    rows_rejected INTEGER NOT NULL
);
"""


def normalize(row: dict) -> tuple | None:
    """Select public analytical fields and reject unusable records.

    Date strings from source are kept unchanged; no timezone is assumed.
    """
    if not row.get("unique_key") or not row.get("created_date"):
        return None
    try:
        datetime.fromisoformat(row["created_date"].replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None
    return tuple(row.get(col) for col in COLUMNS)


def fetch_pages(mode: str, days: int, max_records: int, page_size: int = 1000):
    """Fetch a bounded sample or all records in the selected date window.

    Mode 'created' loads newly created cases; mode 'updated' refreshes changed
    cases, including previously created cases changed in this date window.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
    time_column = "created_date" if mode == "created" else "update_date"
    offset = 0
    while True:
        remaining = max_records - offset if max_records else page_size
        if max_records and remaining <= 0:
            break
        count = min(page_size, remaining)
        params = {
            "$select": ",".join(COLUMNS),
            "$where": f"{time_column} >= '{cutoff}'",
            "$order": f"{time_column} DESC,unique_key DESC",
            "$limit": count,
            "$offset": offset,
        }
        headers = {"User-Agent": "Dallas311PortfolioLearningProject/0.1"}
        token = os.environ.get("SOCRATA_APP_TOKEN")
        if token:
            headers["X-App-Token"] = token
        url = API + "?" + urlencode(params)
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=40) as response:
                batch = json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"Dallas OpenData API request failed: {exc}") from exc
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected API response: expected a JSON array")
        if not batch:
            break
        yield batch
        offset += len(batch)
        if len(batch) < count:
            break


def init_db(connection: sqlite3.Connection) -> None:
    connection.executescript(DDL)


def upsert_batch(connection: sqlite3.Connection, rows: list[dict]) -> tuple[int, int]:
    valid = [v for row in rows if (v := normalize(row)) is not None]
    cols = ",".join(COLUMNS)
    question_marks = ",".join("?" for _ in COLUMNS)
    updates = ",".join(f"{col}=excluded.{col}" for col in COLUMNS if col != "unique_key")
    query = (f"INSERT INTO service_requests ({cols}) VALUES ({question_marks}) "
             f"ON CONFLICT(unique_key) DO UPDATE SET {updates} "
             "WHERE service_requests.update_date IS NULL "
             "OR (excluded.update_date IS NOT NULL "
             "AND excluded.update_date >= service_requests.update_date)")
    with connection:
        connection.executemany(query, valid)
    return len(valid), len(rows) - len(valid)


def write_report(connection: sqlite3.Connection, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    queries = {
        "request_types.csv": """
            SELECT service_request_type, COUNT(*) AS request_count,
                   SUM(CASE WHEN closed_date IS NOT NULL THEN 1 ELSE 0 END) AS with_close_date_count,
                   ROUND(AVG(CASE WHEN closed_date IS NOT NULL
                                      AND julianday(closed_date)>=julianday(created_date)
                                  THEN 24*(julianday(closed_date)-julianday(created_date))
                                  END), 1) AS avg_closure_hours
              FROM service_requests
             GROUP BY service_request_type ORDER BY request_count DESC LIMIT 30
        """,
        "monthly_counts.csv": """
            SELECT SUBSTR(created_date,1,7) AS created_month,
                   city_council_district, COUNT(*) AS requests
              FROM service_requests
             GROUP BY created_month, city_council_district
             ORDER BY created_month, city_council_district
        """,
        "quality_checks.csv": """
            SELECT COUNT(*) AS total_rows,
                   SUM(CASE WHEN city_council_district IS NULL THEN 1 ELSE 0 END) AS missing_district,
                   SUM(CASE WHEN closed_date IS NOT NULL
                              AND julianday(closed_date)<julianday(created_date) THEN 1 ELSE 0 END)
                              AS negative_closure_durations,
                   SUM(CASE WHEN LOWER(COALESCE(status,'')) LIKE 'closed%'
                              AND closed_date IS NULL THEN 1 ELSE 0 END) AS closed_status_no_date
              FROM service_requests
        """,
    }
    for name, sql in queries.items():
        cur = connection.execute(sql)
        with (out_dir / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([d[0] for d in cur.description])
            writer.writerows(cur.fetchall())


def run(args: argparse.Namespace) -> None:
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    fetched = rejected = 0
    with sqlite3.connect(db) as con:
        init_db(con)
        for batch in fetch_pages(args.mode, args.days, args.max_records):
            _, bad = upsert_batch(con, batch)
            fetched += len(batch)
            rejected += bad
            print(f"Fetched {fetched} rows, rejected {rejected} invalid rows")
        with con:
            con.execute("INSERT INTO pipeline_runs (started_utc, mode, days, rows_fetched, rows_rejected) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (datetime.now(timezone.utc).isoformat(), args.mode, args.days, fetched, rejected))
        write_report(con, Path(args.out))
        count = con.execute("SELECT COUNT(*) FROM service_requests").fetchone()[0]
    print(f"Completed. {count} distinct records in {db}. Reports in {args.out}/")
    if args.max_records:
        print("CAUTION: bounded sample; do not claim citywide conclusions from this run.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dallas 311 portfolio starter pipeline")
    parser.add_argument("--mode", choices=("created", "updated"), default="created")
    parser.add_argument("--days", type=int, default=30, help="lookback days, default 30")
    parser.add_argument("--max-records", type=int, default=1000,
                        help="number of API rows to fetch; 0 means no cap")
    parser.add_argument("--db", default="dallas311.sqlite")
    parser.add_argument("--out", default="reports")
    args = parser.parse_args()
    if args.days <= 0 or args.max_records < 0:
        parser.error("--days must be positive and --max-records nonnegative")
    run(args)
