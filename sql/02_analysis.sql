-- Lifecycle & Status Evolution (SCD Type 2) -- BigQuery Standard SQL
-- Replace `your-project.anime_dw` and the snapshot date as needed.
DECLARE snapshot DATE DEFAULT DATE '2026-06-30';
DECLARE min_votes INT64 DEFAULT 100;   -- ignore scores with too few raters

-- Base view: one row per title with engagement metrics
CREATE OR REPLACE VIEW `your-project.anime_dw.v_engagement` AS
SELECT
  f.anime_id, a.name, f.media_key, m.media_type, f.score, f.scored_by,
  f.members, f.favourites, f.aired_start, f.aired_end,
  SAFE_DIVIDE(f.members, GREATEST(DATE_DIFF(DATE '2026-06-30', f.aired_start, DAY) / 365.25, 0.25)) AS members_per_year,   -- "velocity"
  SAFE_DIVIDE(f.favourites, f.members) * 1000 AS favs_per_1k,
  SAFE_DIVIDE(f.scored_by,  f.members)        AS rating_participation
FROM `your-project.anime_dw.fact_sales_series` f
JOIN `your-project.anime_dw.dim_anime` a USING (anime_id)
JOIN `your-project.anime_dw.dim_media_format` m USING (media_key);

-- Q1. Engagement and rating by lifecycle status (current SCD2 row)
SELECT s.status, COUNT(*) AS titles,
  ROUND(AVG(IF(e.scored_by >= min_votes, e.score, NULL)), 2) AS avg_score,
  CAST(APPROX_QUANTILES(e.members_per_year, 100)[OFFSET(50)] AS INT64) AS median_velocity,
  ROUND(APPROX_QUANTILES(e.favs_per_1k, 100)[OFFSET(50)], 2) AS median_favs_per_1k,
  ROUND(APPROX_QUANTILES(e.rating_participation, 100)[OFFSET(50)], 3) AS median_rating_participation
FROM `your-project.anime_dw.v_engagement` e
JOIN `your-project.anime_dw.dim_anime_status_scd2` s ON s.anime_id = e.anime_id AND s.is_current
GROUP BY s.status ORDER BY titles DESC;

-- Q2. Same-cohort comparison (TV, started 2023+): Currently vs Finished Airing
SELECT s.status, COUNT(*) AS titles,
  ROUND(AVG(IF(e.scored_by >= min_votes, e.score, NULL)), 2) AS avg_score,
  CAST(APPROX_QUANTILES(e.members, 100)[OFFSET(50)] AS INT64) AS median_members,
  ROUND(APPROX_QUANTILES(e.favs_per_1k, 100)[OFFSET(50)], 2) AS median_favs_per_1k
FROM `your-project.anime_dw.v_engagement` e
JOIN `your-project.anime_dw.dim_anime_status_scd2` s ON s.anime_id = e.anime_id AND s.is_current
WHERE e.media_type = 'TV' AND EXTRACT(YEAR FROM e.aired_start) >= 2023
  AND s.status IN ('Currently Airing', 'Finished Airing')
GROUP BY s.status;

-- Q3. Post-finish life: how engagement/ratings look N years after the
--     SCD2 'Finished Airing' row became effective (TV only)
SELECT
  CASE WHEN yrs <= 1 THEN '0-1y' WHEN yrs <= 3 THEN '1-3y' WHEN yrs <= 5 THEN '3-5y'
       WHEN yrs <= 10 THEN '5-10y' WHEN yrs <= 20 THEN '10-20y' ELSE '20y+' END AS years_since_finished,
  COUNT(*) AS titles,
  ROUND(AVG(IF(scored_by >= min_votes, score, NULL)), 2) AS avg_score,
  CAST(APPROX_QUANTILES(members, 100)[OFFSET(50)] AS INT64) AS median_members,
  ROUND(APPROX_QUANTILES(favs_per_1k, 100)[OFFSET(50)], 2) AS median_favs_per_1k
FROM (
  SELECT e.*, DATE_DIFF(snapshot, s.valid_from, DAY) / 365.25 AS yrs
  FROM `your-project.anime_dw.v_engagement` e
  JOIN `your-project.anime_dw.dim_anime_status_scd2` s ON s.anime_id = e.anime_id AND s.is_current
  WHERE s.status = 'Finished Airing' AND s.valid_from IS NOT NULL AND e.media_type = 'TV'
)
WHERE yrs > 0
GROUP BY years_since_finished
ORDER BY MIN(yrs);

-- Q4. Studio tier at time of release (point-in-time join to SCD2)
SELECT t.tier, COUNT(*) AS titles,
  ROUND(AVG(IF(e.scored_by >= min_votes, e.score, NULL)), 2) AS avg_score,
  CAST(APPROX_QUANTILES(e.members, 100)[OFFSET(50)] AS INT64) AS median_members
FROM `your-project.anime_dw.v_engagement` e
JOIN `your-project.anime_dw.dim_studio_publisher` sp ON sp.anime_id = e.anime_id AND sp.studio_name != 'UNKNOWN'
JOIN `your-project.anime_dw.dim_studio_tier_scd2` t
  ON t.studio_name = sp.studio_name
 AND EXTRACT(YEAR FROM e.aired_start) BETWEEN t.valid_from_year AND t.valid_to_year
GROUP BY t.tier ORDER BY t.tier;

-- Q5. Studios promoted to a higher tier: titles 5y before vs 5y after promotion
WITH promos AS (
  SELECT studio_name, valid_from_year AS promo_year, tier_rank,
         LAG(tier_rank) OVER (PARTITION BY studio_name ORDER BY valid_from_year) AS prev_rank
  FROM `your-project.anime_dw.dim_studio_tier_scd2`
),
up AS (SELECT * FROM promos WHERE prev_rank IS NOT NULL AND tier_rank < prev_rank)
SELECT IF(EXTRACT(YEAR FROM e.aired_start) < u.promo_year, 'before promotion', 'after promotion') AS period,
  COUNT(*) AS titles,
  ROUND(AVG(IF(e.scored_by >= min_votes, e.score, NULL)), 2) AS avg_score,
  CAST(APPROX_QUANTILES(e.members, 100)[OFFSET(50)] AS INT64) AS median_members
FROM up u
JOIN `your-project.anime_dw.dim_studio_publisher` sp ON sp.studio_name = u.studio_name
JOIN `your-project.anime_dw.v_engagement` e ON e.anime_id = sp.anime_id
WHERE EXTRACT(YEAR FROM e.aired_start) BETWEEN u.promo_year - 5 AND u.promo_year + 4
GROUP BY period;
