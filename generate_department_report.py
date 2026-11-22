
import csv
import sqlite3
from pathlib import Path

# Locate our existing database and reports folder
folder = Path(__file__).resolve().parent
database = folder / "dallas311.sqlite"
output = folder / "reports" / "department_active_rates.csv"

# Our SQL analysis
query = """
SELECT
    department,
    COUNT(*) AS total_requests,
    SUM(
        CASE
            WHEN status IN ('New', 'In Progress')
            THEN 1
            ELSE 0
        END
    ) AS active_requests,
    ROUND(
        100.0 * SUM(
            CASE
                WHEN status IN ('New', 'In Progress')
                THEN 1
                ELSE 0
            END
        ) / COUNT(*),
        1
    ) AS active_percentage
FROM service_requests
GROUP BY department
HAVING COUNT(*) >= 10
ORDER BY active_percentage DESC
LIMIT 10;
"""

# Run the SQL query against SQLite
with sqlite3.connect(database) as connection:
    results = connection.execute(query).fetchall()

# Create the CSV report
output.parent.mkdir(parents=True, exist_ok=True)

with output.open("w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow([
        "department",
        "total_requests",
        "active_requests",
        "active_percentage"
    ])
    writer.writerows(results)

print(f"Report generated: {output}")
print(f"Departments included: {len(results)}")

print("\nTop 3 departments:")

for department, total, active, percentage in results[:3]:
    print(f"{department}: {active}/{total} active ({percentage}%)")
    