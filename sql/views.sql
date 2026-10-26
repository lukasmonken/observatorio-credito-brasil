DROP VIEW IF EXISTS v_latest;
CREATE VIEW v_latest AS
WITH ranked AS (
 SELECT o.*, ROW_NUMBER() OVER(PARTITION BY code ORDER BY date DESC) AS rn
 FROM monthly_observations o WHERE value IS NOT NULL
)
SELECT r.code,s.name,s.unit,s.segment,r.date,r.value,r.run_id
FROM ranked r JOIN series s ON s.code=r.code WHERE rn=1;

DROP VIEW IF EXISTS v_coverage;
CREATE VIEW v_coverage AS
SELECT s.code,s.name,s.unit,MIN(o.date) AS first_date,MAX(o.date) AS last_date,
 COUNT(o.value) AS observed_months,COUNT(o.date)-COUNT(o.value) AS missing_months
FROM series s LEFT JOIN monthly_observations o ON o.code=s.code GROUP BY s.code,s.name,s.unit;

DROP VIEW IF EXISTS v_monthly_changes;
CREATE VIEW v_monthly_changes AS
WITH windows AS (
 SELECT o.*,LAG(value) OVER(PARTITION BY code ORDER BY date) AS previous,
 LAG(value,12) OVER(PARTITION BY code ORDER BY date) AS previous_year,
 AVG(value) OVER(PARTITION BY code ORDER BY date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS average3,
 COUNT(value) OVER(PARTITION BY code ORDER BY date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS count3
 FROM monthly_observations o
)
SELECT w.code,s.name,s.unit,w.date,w.value,
 CASE WHEN s.measure_type IN ('stock','flow','index') THEN 100.0*(w.value/NULLIF(w.previous,0)-1) END AS mom_pct,
 CASE WHEN s.measure_type IN ('stock','flow','index') THEN 100.0*(w.value/NULLIF(w.previous_year,0)-1) END AS yoy_pct,
 CASE WHEN s.measure_type='rate' THEN w.value-w.previous END AS diff_pp,
 CASE WHEN w.count3=3 THEN w.average3 END AS ma3
FROM windows w JOIN series s ON s.code=w.code;
