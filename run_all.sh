#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "STEP 1: Updating Dallas 311 database..."
.venv/bin/python pipeline.py --days 30 --max-records 5000 --db dallas311.sqlite

echo "STEP 2: Generating CSV reports..."
.venv/bin/python generate_department_report.py

echo "STEP 3: Generating charts..."
.venv/bin/python charts.py

echo "DONE! Database, reports, and charts updated."