-- 01_build_star_schema.sql
-- Builds the two star-schema tables Question 2 needs from the raw CSV staging table:
--   dim_anime  (PK anime_id; holds members, score, scored_by, status, type, episodes)
--   dim_genre  (PK genre_id; FK title -> dim_anime.name; one row per title per genre tag)
-- Placeholders {project} and {dataset} are filled in by q2_audience_retention.py.

CREATE OR REPLACE TABLE `{project}.{dataset}.dim_anime` AS
SELECT
  CAST(anime_id AS INT64)                                   AS anime_id,
  name,
  NULLIF(english_name, 'UNKNOWN')                           AS english_name,
  NULLIF(other_name,   'UNKNOWN')                           AS other_name,
  SAFE_CAST(NULLIF(score, 'UNKNOWN') AS NUMERIC)            AS score,        -- DECIMAL(3,2)
  genres,
  NULLIF(synopsis, 'UNKNOWN')                               AS synopsis,
  type,
  SAFE_CAST(NULLIF(episodes, 'UNKNOWN') AS INT64)           AS episodes,
  aired,
  NULLIF(premiered, 'UNKNOWN')                              AS premiered,
  status,
  NULLIF(producers, 'UNKNOWN')                              AS producer,
  NULLIF(licensors, 'UNKNOWN')                              AS licensors,
  NULLIF(studios,   'UNKNOWN')                              AS studios,
  NULLIF(source,    'UNKNOWN')                              AS source,
  duration,
  rating,
  SAFE_CAST(NULLIF(rank, 'UNKNOWN') AS INT64)               AS rank,
  SAFE_CAST(popularity AS INT64)                            AS popularity,
  SAFE_CAST(favourites AS INT64)                            AS favourites,
  SAFE_CAST(NULLIF(scored_by, 'UNKNOWN') AS INT64)          AS scored_by,
  SAFE_CAST(members AS INT64)                               AS members
FROM `{project}.{dataset}.stg_anime_dataset`;

CREATE OR REPLACE TABLE `{project}.{dataset}.dim_genre` AS
SELECT
  ROW_NUMBER() OVER (ORDER BY a.anime_id, tag)              AS genre_id,
  a.name                                                    AS title,         -- FK -> dim_anime.name
  TRIM(tag)                                                 AS genre_name,
  IF(TRIM(tag) IN ('Shounen','Shoujo','Seinen','Josei','Kids'),
     TRIM(tag), NULL)                                       AS demographic
FROM `{project}.{dataset}.dim_anime` AS a,
     UNNEST(SPLIT(a.genres, ', ')) AS tag
WHERE a.genres IS NOT NULL AND a.genres != 'UNKNOWN';
