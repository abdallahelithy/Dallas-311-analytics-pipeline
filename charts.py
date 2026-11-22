
import sqlite3
from pathlib import Path
import matplotlib.pyplot as plt

folder = Path(__file__).resolve().parent
database = folder / "dallas311.sqlite"
reports = folder / "reports"
reports.mkdir(exist_ok=True)

with sqlite3.connect(database) as db:
    # Chart 1: Most common service request types
    request_types = db.execute("""
        SELECT service_request_type, COUNT(*) AS total
        FROM service_requests
        WHERE service_request_type IS NOT NULL
        GROUP BY service_request_type
        ORDER BY total DESC
        LIMIT 10
    """).fetchall()

    # Chart 2: Departments with the most active requests
    departments = db.execute("""
        SELECT department, COUNT(*) AS active
        FROM service_requests
        WHERE status IN ('New', 'In Progress')
          AND department IS NOT NULL
        GROUP BY department
        ORDER BY active DESC
        LIMIT 10
    """).fetchall()


def make_chart(data, title, filename, xlabel):
    if not data:
        print(f"No data available for {filename}")
        return

    names = [row[0] for row in data]
    counts = [row[1] for row in data]

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(names, counts)
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel(xlabel)

    fig.tight_layout()
    fig.savefig(reports / filename, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"Created: {filename}")


make_chart(
    request_types,
    "Top 10 Dallas 311 Request Types - Sample",
    "top_request_types.png",
    "Number of requests"
)

make_chart(
    departments,
    "Top 10 Departments by Active Requests - Sample",
    "active_requests_by_department.png",
    "Active requests"
)
