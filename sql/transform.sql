-- ============================================================================
-- 1. FACT TABLE: fact_sales_series
-- Source CSVs: data/series_sales.csv & data/series_sales_v2.csv
-- CSV Headers: index,media_type,title,jp_title,period_type,raw_period,volume,sales
-- ============================================================================
CREATE OR REPLACE TABLE `{project_id}.{dataset}.fact_sales_series`
CLUSTER BY title, media_key, raw_period
AS
WITH combined_staging AS (
  SELECT index, media_type, title, jp_title, period_type, raw_period, volume, sales
  FROM `{project_id}.anime_staging.series_sales`
  UNION ALL
  SELECT index, media_type, title, jp_title, period_type, raw_period, volume, sales
  FROM `{project_id}.anime_staging.series_sales_v2`
),
parsed_sales AS (
  SELECT
    CASE UPPER(TRIM(media_type))
      WHEN 'MANGA' THEN 1
      WHEN 'LIGHT NOVEL' THEN 2
      WHEN 'ANIME' THEN 3
      ELSE -1
    END AS media_key,
    TRIM(title) AS title,
    TRIM(title) AS en_title,
    TRIM(jp_title) AS jp_title,
    UPPER(TRIM(COALESCE(period_type, 'UNKNOWN'))) AS period_type,
    -- Encode 'Oct 2009' -> 200910 (YYYYMM) and '2025' -> 202500 (YYYY00) as INT64
    COALESCE(
      CAST(FORMAT_DATE('%Y%m', SAFE.PARSE_DATE('%b %Y', TRIM(CAST(raw_period AS STRING)))) AS INT64),
      SAFE_CAST(TRIM(CAST(raw_period AS STRING)) AS INT64) * 100,
      -1
    ) AS raw_period,
    -- 'Series total' becomes 0; numeric volumes become their integer number
    COALESCE(SAFE_CAST(REGEXP_EXTRACT(CAST(volume AS STRING), r'(\d+)') AS INT64), 0) AS volume,
    SAFE_CAST(sales AS INT64) AS sales
  FROM combined_staging
  WHERE title IS NOT NULL AND TRIM(title) != ''
)
SELECT
  FARM_FINGERPRINT(CONCAT(
    UPPER(title), '|',
    CAST(media_key AS STRING), '|',
    period_type, '|',
    CAST(raw_period AS STRING), '|',
    CAST(volume AS STRING)
  )) AS id,
  media_key,
  title,
  ANY_VALUE(en_title) AS en_title,
  ANY_VALUE(jp_title) AS jp_title,
  period_type,
  raw_period,
  volume,
  MAX(sales) AS sales
FROM parsed_sales
GROUP BY media_key, title, period_type, raw_period, volume;


-- ============================================================================
-- 2. DIMENSION TABLE: dim_anime
-- Source CSV: data/anime-dataset-2026.csv
-- CSV Headers: anime_id,Name,English name,Other name,Score,Genres,Synopsis,Type,
--              Episodes,Aired,Premiered,Status,Producers,Licensors,Studios,
--              Source,Duration,Rating,Rank,Popularity,Favorites,Scored By,Members,Image URL
-- ============================================================================
CREATE OR REPLACE TABLE `{project_id}.{dataset}.dim_anime` AS
SELECT
  SAFE_CAST(anime_id AS INT64) AS anime_id,
  COALESCE(ANY_VALUE(TRIM(Name)), 'UNKNOWN') AS title,
  COALESCE(NULLIF(ANY_VALUE(TRIM(`English name`)), 'UNKNOWN'), ANY_VALUE(TRIM(Name)), 'UNKNOWN') AS en_title,
  ANY_VALUE(TRIM(`Other name`)) AS jp_title,
  ANY_VALUE(SAFE_CAST(Score AS NUMERIC)) AS score,
  ANY_VALUE(ARRAY(
    SELECT TRIM(g) FROM UNNEST(SPLIT(Genres, ',')) AS g WHERE TRIM(g) != '' AND TRIM(g) != 'UNKNOWN'
  )) AS genres,
  ANY_VALUE(TRIM(Synopsis)) AS synopsis,
  ANY_VALUE(TRIM(Type)) AS type,
  ANY_VALUE(SAFE_CAST(Episodes AS INT64)) AS episodes,
  ANY_VALUE(TRIM(Aired)) AS aired,
  ANY_VALUE(TRIM(Premiered)) AS premiered,
  ANY_VALUE(TRIM(Status)) AS status,
  ANY_VALUE(ARRAY(SELECT TRIM(p) FROM UNNEST(SPLIT(Producers, ',')) AS p WHERE TRIM(p) != '' AND TRIM(p) != 'UNKNOWN')) AS producers,
  ANY_VALUE(ARRAY(SELECT TRIM(l) FROM UNNEST(SPLIT(Licensors, ',')) AS l WHERE TRIM(l) != '' AND TRIM(l) != 'UNKNOWN')) AS licensors,
  ANY_VALUE(ARRAY(SELECT TRIM(s) FROM UNNEST(SPLIT(Studios, ',')) AS s WHERE TRIM(s) != '' AND TRIM(s) != 'UNKNOWN')) AS studios,
  ANY_VALUE(TRIM(Source)) AS source,
  ANY_VALUE(TRIM(Duration)) AS duration,
  ANY_VALUE(TRIM(Rating)) AS rating,
  COALESCE(ANY_VALUE(SAFE_CAST(Rank AS INT64)), 0) AS rank,
  COALESCE(ANY_VALUE(SAFE_CAST(Popularity AS INT64)), 0) AS popularity,
  ANY_VALUE(SAFE_CAST(Favorites AS INT64)) AS favourites,
  ANY_VALUE(SAFE_CAST(`Scored By` AS INT64)) AS scored_by,
  COALESCE(ANY_VALUE(SAFE_CAST(Members AS INT64)), 0) AS members
FROM `{project_id}.anime_staging.anime_dataset_2026`
WHERE SAFE_CAST(anime_id AS INT64) IS NOT NULL
GROUP BY anime_id;


-- ============================================================================
-- 3. DIMENSION TABLE: dim_media_format
-- ============================================================================
CREATE OR REPLACE TABLE `{project_id}.{dataset}.dim_media_format` AS
SELECT 1 AS media_key, 'Manga' AS media_type UNION ALL
SELECT 2 AS media_key, 'Light Novel' AS media_type UNION ALL
SELECT 3 AS media_key, 'Anime' AS media_type UNION ALL
SELECT -1 AS media_key, 'Unknown' AS media_type;


-- ============================================================================
-- 4. DIMENSION TABLE: dim_date_period
-- Source CSVs: data/series_sales.csv & data/series_sales_v2.csv (period_type, raw_period)
-- ============================================================================
CREATE OR REPLACE TABLE `{project_id}.{dataset}.dim_date_period` AS
WITH combined_periods AS (
  SELECT DISTINCT period_type, CAST(raw_period AS STRING) AS raw_period_str
  FROM (
    SELECT period_type, raw_period FROM `{project_id}.anime_staging.series_sales`
    UNION ALL
    SELECT period_type, raw_period FROM `{project_id}.anime_staging.series_sales_v2`
  )
  WHERE raw_period IS NOT NULL
),
parsed_dates AS (
  SELECT
    UPPER(TRIM(COALESCE(period_type, 'UNKNOWN'))) AS period_type,
    SAFE.PARSE_DATE('%b %Y', TRIM(raw_period_str)) AS parsed_month_date,
    SAFE_CAST(TRIM(raw_period_str) AS INT64) AS parsed_year_only
  FROM combined_periods
),
enriched AS (
  SELECT
    COALESCE(
      CAST(FORMAT_DATE('%Y%m', parsed_month_date) AS INT64),
      parsed_year_only * 100
    ) AS period_key,
    period_type,
    COALESCE(EXTRACT(YEAR FROM parsed_month_date), parsed_year_only) AS year,
    EXTRACT(MONTH FROM parsed_month_date) AS month_num
  FROM parsed_dates
)
SELECT
  period_key,
  ANY_VALUE(period_type) AS period_type,
  ANY_VALUE(year) AS year,
  ANY_VALUE(month_num) AS month_num,
  CASE
    WHEN ANY_VALUE(month_num) BETWEEN 1 AND 3 THEN 'Q1'
    WHEN ANY_VALUE(month_num) BETWEEN 4 AND 6 THEN 'Q2'
    WHEN ANY_VALUE(month_num) BETWEEN 7 AND 9 THEN 'Q3'
    WHEN ANY_VALUE(month_num) BETWEEN 10 AND 12 THEN 'Q4'
    ELSE NULL
  END AS quarter,
  CASE
    WHEN ANY_VALUE(month_num) IN (1, 2, 3) THEN 'Winter'
    WHEN ANY_VALUE(month_num) IN (4, 5, 6) THEN 'Spring'
    WHEN ANY_VALUE(month_num) IN (7, 8, 9) THEN 'Summer'
    WHEN ANY_VALUE(month_num) IN (10, 11, 12) THEN 'Fall'
    ELSE NULL
  END AS anime_season
FROM enriched
WHERE period_key IS NOT NULL
GROUP BY period_key;


-- ============================================================================
-- 5. DIMENSION TABLE: dim_studio_publisher
-- Source CSVs: data/anime-dataset-2026.csv (Name, Studios, Producers)
--              & data/manga_dataset.csv (title, serializations)
-- ============================================================================
CREATE OR REPLACE TABLE `{project_id}.{dataset}.dim_studio_publisher` AS
WITH anime_orgs AS (
  SELECT
    TRIM(Name) AS title,
    TRIM(studio) AS studio_name,
    NULLIF(TRIM(SPLIT(Producers, ',')[SAFE_OFFSET(0)]), 'UNKNOWN') AS publisher_name
  FROM `{project_id}.anime_staging.anime_dataset_2026`,
  UNNEST(SPLIT(Studios, ',')) AS studio
  WHERE Name IS NOT NULL AND TRIM(studio) != '' AND TRIM(studio) != 'UNKNOWN'
),
manga_mags AS (
  SELECT
    TRIM(title) AS title,
    ANY_VALUE(NULLIF(TRIM(serializations), '')) AS magazine_name
  FROM `{project_id}.anime_staging.manga_dataset`
  WHERE title IS NOT NULL
  GROUP BY TRIM(title)
)
SELECT
  FARM_FINGERPRINT(CONCAT(UPPER(a.title), '|', UPPER(a.studio_name))) AS org_id,
  a.title,
  a.studio_name,
  ANY_VALUE(a.publisher_name) AS publisher_name,
  ANY_VALUE(m.magazine_name) AS magazine_name
FROM anime_orgs a
LEFT JOIN manga_mags m
  ON UPPER(a.title) = UPPER(m.title)
GROUP BY a.title, a.studio_name;


-- ============================================================================
-- 6. DIMENSION TABLE: dim_author
-- Source CSV: data/manga_dataset.csv
-- CSV Headers: mal_id,title,title_english,title_japanese,type,chapters,volumes,
--              status,publishing,published_from,published_to,score,scored_by,
--              rank,popularity,members,favorites,authors,serializations,genres,
--              themes,demographics,synopsis,image_url
-- ============================================================================
CREATE OR REPLACE TABLE `{project_id}.{dataset}.dim_author` AS
WITH authors_clean AS (
  SELECT DISTINCT
    TRIM(title)   AS title,
    TRIM(authors) AS author_name
  FROM `{project_id}.anime_staging.manga_dataset`
  WHERE title IS NOT NULL
    AND authors IS NOT NULL
    AND TRIM(authors) != ''
)
SELECT
  FARM_FINGERPRINT(CONCAT(UPPER(title), '|', UPPER(author_name))) AS author_id,
  title,
  author_name,
  'Story & Art' AS role
FROM authors_clean;


-- ============================================================================
-- 7. DIMENSION TABLE: dim_genre
-- Source CSVs: data/manga_dataset.csv (title, genres [pipe-separated], demographics)
--              & data/anime-dataset-2026.csv (Name, Genres [comma-separated])
-- ============================================================================
CREATE OR REPLACE TABLE `{project_id}.{dataset}.dim_genre` AS
WITH manga_genres AS (
  SELECT
    TRIM(title) AS title,
    TRIM(g) AS genre_name,
    NULLIF(TRIM(demographics), '') AS demographic
  FROM `{project_id}.anime_staging.manga_dataset`,
  UNNEST(SPLIT(genres, '|')) AS g
  WHERE title IS NOT NULL AND TRIM(g) != ''
),
anime_genres AS (
  SELECT
    TRIM(Name) AS title,
    TRIM(g) AS genre_name,
    CAST(NULL AS STRING) AS demographic
  FROM `{project_id}.anime_staging.anime_dataset_2026`,
  UNNEST(SPLIT(Genres, ',')) AS g
  WHERE Name IS NOT NULL AND TRIM(g) != '' AND TRIM(g) != 'UNKNOWN'
),
combined_genres AS (
  SELECT * FROM manga_genres
  UNION ALL
  SELECT * FROM anime_genres
)
SELECT
  FARM_FINGERPRINT(CONCAT(UPPER(title), '|', UPPER(genre_name))) AS genre_id,
  title,
  genre_name,
  ANY_VALUE(demographic) AS demographic
FROM combined_genres
GROUP BY title, genre_name;
