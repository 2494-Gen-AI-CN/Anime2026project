WITH yearly_sales AS (
        SELECT
            TRIM(S.title) AS title,
            D.year,
            MAX(S.sales) AS yearly_sales
        FROM `{project_id}.{dataset}.fact_sales_series` S
        JOIN `{project_id}.{dataset}.dim_date_period` D
            ON S.raw_period = D.period_key
        GROUP BY TRIM(S.title), D.year
    ),

anime_dates AS (
        SELECT
            Y.title,
            MIN(SAFE_CAST(REGEXP_EXTRACT(SPLIT(A.aired, ' to ')[SAFE_OFFSET(0)], r'(\d{{4}})') AS INT64)) AS start_year,
            MAX(SAFE_CAST(REGEXP_EXTRACT(
                COALESCE(SPLIT(A.aired, ' to ')[SAFE_OFFSET(1)], SPLIT(A.aired, ' to ')[SAFE_OFFSET(0)]),
                r'(\d{{4}})'
            ) AS INT64)) AS end_year
        FROM (SELECT DISTINCT title FROM yearly_sales) Y
        JOIN `{project_id}.{dataset}.dim_anime` A
            ON TRIM(UPPER(Y.title)) IN (TRIM(UPPER(A.title)), TRIM(UPPER(A.en_title)))
        WHERE A.type IN ('TV', 'ONA')
        GROUP BY Y.title
    )

SELECT
    Y.title AS title,
    A.start_year AS start_year,
    A.end_year AS end_year,
    MAX(CASE WHEN Y.year = A.start_year - 1 THEN Y.yearly_sales END) AS sales_before,
    SUM(CASE WHEN Y.year BETWEEN A.start_year AND A.end_year THEN Y.yearly_sales END) AS sales_during,
    MAX(CASE WHEN Y.year = A.end_year + 1   THEN Y.yearly_sales END) AS sales_after,
FROM yearly_sales Y
JOIN anime_dates A
    ON Y.title = A.title
WHERE UPPER(Y.title) IN (
        'JUJUTSU KAISEN',
        'KIMETSU NO YAIBA',
        'BLUE LOCK',
        'CHAINSAW MAN',
        "FRIEREN: BEYOND JOURNEY'S END",
        'THE APOTHECARY DIARIES'
    )
GROUP BY Y.title, A.start_year, A.end_year
HAVING sales_before > 0
   AND sales_after > 0
