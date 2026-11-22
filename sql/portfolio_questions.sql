-- Questions to investigate AFTER the initial sample is replaced by a complete backfill.
-- 1. Which request types have the largest queues? Note that closure ≠ resolved.
SELECT service_request_type, status, COUNT(*) AS requests
FROM service_requests
GROUP BY service_request_type, status
ORDER BY requests DESC LIMIT 30;

-- 2. Among dated closures, which departments have the longest average turnaround?
-- Limitations: averages are affected by request category mix and outliers.
SELECT department,
       COUNT(*) AS closure_count,
       ROUND(AVG(24*(julianday(closed_date)-julianday(created_date))),1) AS mean_hours
FROM service_requests
WHERE closed_date IS NOT NULL
  AND julianday(closed_date) >= julianday(created_date)
GROUP BY department
ORDER BY mean_hours DESC;

-- 3. Which districts have most reported requests?
-- Raw counts are NOT adjusted for population, reporting rates, or case type.
SELECT city_council_district, COUNT(*) AS total
FROM service_requests
GROUP BY city_council_district
ORDER BY total DESC;