import json
import os
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pipeline import API, COLUMNS, init_db, upsert_batch, write_report

DATABASE = Path("dallas311.sqlite")
CUTOFF = "2025-11-22T00:00:00"
PAGE_SIZE = 1000


def escape(value):
    return str(value).replace("'", "''")


with sqlite3.connect(DATABASE) as db:
    init_db(db)

    # Find where the previous download stopped
    cursor = db.execute("""
        SELECT created_date, unique_key
        FROM service_requests
        WHERE created_date >= ?
        ORDER BY created_date ASC, unique_key ASC
        LIMIT 1
    """, (CUTOFF,)).fetchone()

    print("Resuming from:", cursor, flush=True)

    while True:
        condition = f"created_date >= '{CUTOFF}'"

        if cursor:
            date, key = cursor
            condition += (
                f" AND (created_date < '{escape(date)}'"
                f" OR (created_date = '{escape(date)}'"
                f" AND unique_key < '{escape(key)}'))"
            )

        params = {
            "$select": ",".join(COLUMNS),
            "$where": condition,
            "$order": "created_date DESC,unique_key DESC",
            "$limit": PAGE_SIZE,
        }

        url = API + "?" + urlencode(params)
        headers = {"User-Agent": "Dallas311PortfolioLearningProject/0.1"}

        if os.environ.get("SOCRATA_APP_TOKEN"):
            headers["X-App-Token"] = os.environ["SOCRATA_APP_TOKEN"]

        # Retry temporary network failures
        for attempt in range(7):
            try:
                with urlopen(Request(url, headers=headers), timeout=90) as response:
                    batch = json.load(response)
                break
            except (OSError, ValueError) as error:
                if attempt == 6:
                    raise
                wait = min(60, 2 ** (attempt + 1))
                print(f"Request failed: {error}. Retrying in {wait}s...")
                time.sleep(wait)

        if not isinstance(batch, list):
            raise RuntimeError("Unexpected API response")

        if not batch:
            print("Historical download complete!")
            break

        valid, rejected = upsert_batch(db, batch)

        # Advance to the last downloaded request
        last = batch[-1]
        cursor = (last["created_date"], last["unique_key"])

        total = db.execute(
            "SELECT COUNT(*) FROM service_requests"
        ).fetchone()[0]

        print(
            f"Database: {total:,} records | "
            f"New batch: {valid} valid, {rejected} rejected",
            flush=True
        )

    write_report(db, Path("reports"))

print("Finished. Historical records saved.")
