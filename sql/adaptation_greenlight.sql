-- 1. Get yearly sales per series from fact_sales_series + dim_date_period
WITH yearly_sales AS (
    SELECT
        TRIM(f.title) AS title,
        ANY_VALUE(NULLIF(TRIM(f.jp_title), '')) AS jp_title,
        d.year,
        MAX(f.sales) AS yearly_sales
    FROM `{project_id}.{dataset}.fact_sales_series` f
    JOIN `{project_id}.{dataset}.dim_date_period` d
      ON f.raw_period = d.period_key
    GROUP BY TRIM(f.title), d.year
),

first_anime AS (
    SELECT
        s.title,
        MIN(SAFE_CAST(REGEXP_EXTRACT(a.aired, r'(\d{{4}})') AS INT64)) AS first_air_year
    FROM (SELECT title, ANY_VALUE(jp_title) AS jp_title FROM yearly_sales GROUP BY title) s
    JOIN `{project_id}.{dataset}.dim_anime` a
      ON NULLIF(REGEXP_REPLACE(LOWER(s.title), r'[^a-z0-9]', ''), '') IN (
             NULLIF(REGEXP_REPLACE(LOWER(a.title), r'[^a-z0-9]', ''), ''),
             NULLIF(REGEXP_REPLACE(LOWER(a.en_title), r'[^a-z0-9]', ''), '')
         )
      OR TRIM(s.jp_title) = TRIM(a.jp_title)
    WHERE a.type IN ('TV', 'ONA')
    GROUP BY s.title
)

-- 3. Combine:
--    - If first_air_year IS NOT NULL -> Adapted series (Training data: before_sales vs after_sales)
--    - If first_air_year IS NULL     -> Unadapted series (Candidates to greenlight: latest_sales)
SELECT
    y.title,
    a.first_air_year,
    CASE WHEN a.first_air_year IS NOT NULL THEN TRUE ELSE FALSE END AS is_adapted,
    -- For adapted series: sales 1 year BEFORE and 1 year AFTER anime aired
    MAX(CASE WHEN y.year = a.first_air_year - 1 THEN y.yearly_sales END) AS sales_before_anime,
    MAX(CASE WHEN y.year = a.first_air_year + 1 THEN y.yearly_sales END) AS sales_after_anime,
    -- For unadapted series: their most recent yearly/annualized baseline sales
    ARRAY_AGG(y.yearly_sales ORDER BY y.year DESC LIMIT 1)[OFFSET(0)] AS latest_baseline_sales
FROM yearly_sales y
LEFT JOIN first_anime a
  ON y.title = a.title
GROUP BY y.title, a.first_air_year;