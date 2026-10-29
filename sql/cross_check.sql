-- Independent cross-check of the pipeline, in SQL.
-- Load the three CSV files from data/reconstructed into a NEW database in
-- DB Browser for SQLite as tables named: contacts, pipeline, revenue.
-- DB Browser imports every column as text, so True/False are compared as text.
-- Run each query on its own. The expected answer is written above each one.

-- 1. Total leads. Expected: 1458
SELECT COUNT(*) AS total_leads FROM contacts;

-- 2. Paid clients by close year. Expected: 2023 = 13, 2024 = 27, 2025 = 50, 2026 = 30
SELECT substr(close_date, 1, 4) AS close_year, COUNT(*) AS paid_clients
FROM pipeline
WHERE closed_won = 'True'
GROUP BY close_year
ORDER BY close_year;

-- 3. Revenue in the report window, Jan 2024 to May 2026. Expected: 4645000
SELECT SUM(total_revenue_bdt) AS revenue_bdt
FROM revenue
WHERE close_date BETWEEN '2024-01-01' AND '2026-05-31';

-- 4. November 2025: paid clients and revenue. Expected: 6 and 270000
SELECT COUNT(*) AS paid_clients, SUM(total_revenue_bdt) AS revenue_bdt
FROM revenue
WHERE close_date BETWEEN '2025-11-01' AND '2025-11-30';

-- 5. Close rate in the November 2025 report: leads that arrived Aug-Oct 2025,
--    counting only those that had paid by 30 Nov 2025. Expected: 20 paid of 205 leads (9.8%)
SELECT SUM(CASE WHEN closed_won = 'True' AND close_date <= '2025-11-30' THEN 1 ELSE 0 END) AS paid,
       COUNT(*) AS leads,
       ROUND(100.0 * SUM(CASE WHEN closed_won = 'True' AND close_date <= '2025-11-30'
                              THEN 1 ELSE 0 END) / COUNT(*), 1) AS close_rate_pct
FROM pipeline
WHERE inquiry_date BETWEEN '2025-08-01' AND '2025-10-31';
