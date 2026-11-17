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
SELECT o.code, s.name, s.unit, o.date, o.value,
       MAX(CASE WHEN d.metric = 'mom_pct' THEN d.value END) AS mom_pct,
       MAX(CASE WHEN d.metric = 'yoy_pct' THEN d.value END) AS yoy_pct,
       MAX(CASE WHEN d.metric = 'diff_pp' THEN d.value END) AS diff_pp,
       MAX(CASE WHEN d.metric = 'ma3' THEN d.value END) AS ma3
FROM monthly_observations o
JOIN series s ON s.code = o.code
LEFT JOIN derived_indicators d ON d.code = o.code AND d.date = o.date
    AND d.run_id = o.run_id AND d.metric IN ('mom_pct', 'yoy_pct', 'diff_pp', 'ma3')
WHERE s.frequency <> 'Q'
GROUP BY o.code, s.name, s.unit, o.date, o.value;
