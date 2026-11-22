# Dallas 311 Service Requests — Technical Portfolio Starter

**Purpose:** Learn an end-to-end pipeline by using live public data, rather than copying a static dashboard tutorial.

**Verified source:** City of Dallas 311 Service Requests (October 1, 2020 to present):
- Portal: https://www.dallasopendata.com/d/d7e7-envw
- Public API: https://www.dallasopendata.com/resource/d7e7-envw.json
- Socrata API documentation: https://dev.socrata.com/consumers/getting-started.html

This starter's fields were inspected against the actual public JSON feed on November 19, 2026. **It is not yet an end-to-end production pipeline**, and a small sample cannot support population-wide findings.

## What it already does
- Downloads data using an HTTP API with optional pagination and date filters
- Explicitly excludes street addresses and precise coordinates to protect privacy
- Rejects records with missing IDs or invalid creation dates
- Upserts into SQLite keyed on source `unique_key` so repeat runs don't create duplicates
- Prevents older updates from replacing newer ones
- Produces CSV reports, including data-quality counts
- Includes two offline tests

## Start on your computer

Requires **Python 3.10+**, no third-party packages to install.

```bash
python -m unittest discover -s tests -v
python pipeline.py --days 30 --max-records 1000
```

The second command needs internet access to the Dallas OpenData API. Outputs:
- `data/dallas311.sqlite` (raw limited source fields)
- `reports/request_types.csv`
- `reports/monthly_counts.csv`
- `reports/quality_checks.csv`

**Important:** Default mode fetches the most recently *created* 1,000 records from the last 30 days, not a random or representative sample. Use this only to verify the system works. Do not publish conclusions based on these bounded rows.

To backfill the entire prior 90-day window (may take time and hit rate limits):

```bash
python pipeline.py --mode created --days 90 --max-records 0
```

To refresh records that changed in the past week (including old cases):

```bash
python pipeline.py --mode updated --days 7 --max-records 0
```

The program does **not** yet track a durable last-successful-run watermark. That is part of the next technical milestone. It currently uses lookback windows. Live offset pagination may shift if the source changes during the run; for a rigorous portfolio, implement a snapshot/watermark or keyset pagination before making full-coverage claims.

Optionally set `SOCRATA_APP_TOKEN` as an environment variable for your app token; do not commit it to GitHub.

## Project question

**Which categories of Dallas 311 requests are experiencing the longest turnaround, and how can a repeatable data-quality-checked report help operations staff find those patterns?**

A strong portfolio result is not merely charts. You must explain:
1. Data source, freshness, and coverage
2. Deduplication and validation rules
3. Treatment of missing, closed, and transferred records
4. The difference between *closed* and *successfully resolved*
5. How comparisons depend on case mix, time window, and reporting biases
6. A reproducible workflow and its limitations

**Do not** store or publish row-level home addresses, precise geographic coordinates, names, or contact information. District-level aggregates are a safer starting point.

## Suggested four-week build sequence

**Week 1:** Understand the API response; run this starter; examine SQLite tables and tests. Explain every line in `normalize()` and `upsert_batch()`.

**Week 2:** Replace the sample with a measured backfill, add incremental checkpointing, test updates and duplicates, and reconcile counts.

**Week 3:** Add SQL analytics for closures and cohorts. Build Power BI visuals from **aggregated data only**. Validate every calculation.

**Week 4:** Schedule controlled reruns, add failure logging and data quality alerts, write a strong README with examples, and prepare a 3-minute explanation for interviews.

## Practice tasks for you
1. Why do we use `unique_key` instead of row number for deduplication?
2. If a case is created in September and closed in November, which mode retrieves its updated status?
3. What could make `AVG(closed_date - created_date)` misleading?
4. Write a SQL query showing the number of cases by department and month.
5. Add a test covering a record where `closed_date` is earlier than `created_date`.

All of these are your work to understand and refine; do not claim the unimplemented pieces are already complete.
