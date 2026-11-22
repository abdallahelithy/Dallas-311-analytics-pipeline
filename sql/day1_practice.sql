-- Query 2: Which departments receive the most requests?

SELECT
    department,
    COUNT(*) AS total_requests
FROM service_requests
GROUP BY department
ORDER BY total_requests DESC
LIMIT 10;