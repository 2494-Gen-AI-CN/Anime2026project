-- 1. Get yearly sales per series from fact_sales_series + dim_date_period
    WITH yearly_sales AS (
        SELECT
            f.title,
            d.year,
            MAX(f.sales) AS yearly_sales
        FROM `{project_id}.{dataset}.fact_sales_series` f
        JOIN `{project_id}.{dataset}.dim_date_period` d
          ON f.raw_period = d.period_key
        GROUP BY f.title, d.year
    ),
    
    -- 2. Find the FIRST TV/ONA anime air year from dim_anime (NULL if never adapted!)
    first_anime AS (
        SELECT
            en_title,
            title AS romaji_title,
            MIN(SAFE_CAST(REGEXP_EXTRACT(aired, r'(\d{{4}})') AS INT64)) AS first_air_year
        FROM `{project_id}.{dataset}.dim_anime`
        WHERE type IN ('TV', 'ONA')
        GROUP BY en_title, romaji_title
    ),
    
    -- 3. Get genre/demographic features from dim_genre
    series_meta AS (
        SELECT
            title,
            MAX(CASE WHEN UPPER(demographic) LIKE '%SHOUNEN%' OR UPPER(genre_name) LIKE '%SHOUNEN%' THEN 1 ELSE 0 END) AS is_shounen
        FROM `{project_id}.{dataset}.dim_genre`
        GROUP BY title
    )
    
    -- 4. Combine:
    --    - If first_air_year IS NOT NULL -> Adapted series (Training data: before_sales vs after_sales)
    --    - If first_air_year IS NULL     -> Unadapted series (Candidates to greenlight: latest_sales)
    SELECT
        y.title,
        a.first_air_year,
        CASE WHEN a.first_air_year IS NOT NULL THEN TRUE ELSE FALSE END AS is_adapted,
        COALESCE(m.is_shounen, 0) AS is_shounen,
        -- For adapted series: sales 1 year BEFORE and 1 year AFTER anime aired
        MAX(CASE WHEN y.year = a.first_air_year - 1 THEN y.yearly_sales END) AS sales_before_anime,
        MAX(CASE WHEN y.year = a.first_air_year + 1 THEN y.yearly_sales END) AS sales_after_anime,
        -- For unadapted series: their most recent yearly/annualized baseline sales
        ARRAY_AGG(y.yearly_sales ORDER BY y.year DESC LIMIT 1)[OFFSET(0)] AS latest_baseline_sales
    FROM yearly_sales y
    LEFT JOIN first_anime a
      ON UPPER(y.title) = UPPER(a.en_title)
    LEFT JOIN series_meta m
      ON UPPER(y.title) = UPPER(m.title)
    GROUP BY y.title, a.first_air_year, m.is_shounen;