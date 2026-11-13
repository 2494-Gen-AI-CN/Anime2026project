-- BigQuery DDL for the star schema (replace `your-project.anime_dw`).
-- Column names follow the ER diagram. Two extensions are marked "-- EXT".

CREATE SCHEMA IF NOT EXISTS `your-project.anime_dw`;

CREATE OR REPLACE TABLE `your-project.anime_dw.dim_anime` (
  anime_id INT64 NOT NULL, name STRING NOT NULL, english_name STRING, other_name STRING,
  score NUMERIC, genres STRING NOT NULL, synopsis STRING, type STRING, episodes INT64,
  aired STRING, premiered STRING, status STRING, producer STRING, licensors STRING,
  studios STRING, source STRING, duration STRING, rating STRING, rank INT64 NOT NULL,
  popularity INT64 NOT NULL, favourites INT64, scored_by INT64, members INT64 NOT NULL
);

CREATE OR REPLACE TABLE `your-project.anime_dw.dim_studio_publisher` (
  org_id INT64 NOT NULL, title STRING NOT NULL, studio_name STRING NOT NULL,
  publisher_name STRING, magazine_name STRING,
  anime_id INT64                                   -- EXT: stable join key (title is not unique)
);

CREATE OR REPLACE TABLE `your-project.anime_dw.dim_author` (
  author_id INT64 NOT NULL, title STRING, author_name STRING NOT NULL, role STRING
);  -- created for completeness; the CSV has no author data

CREATE OR REPLACE TABLE `your-project.anime_dw.dim_media_format` (
  media_key INT64 NOT NULL, media_type STRING NOT NULL, genre_name STRING
);

CREATE OR REPLACE TABLE `your-project.anime_dw.dim_genre` (
  genre_id INT64 NOT NULL, title STRING NOT NULL, genre_name STRING, demographic STRING,
  anime_id INT64                                   -- EXT
);

CREATE OR REPLACE TABLE `your-project.anime_dw.dim_date_period` (
  period_key INT64 NOT NULL, period_type STRING, year INT64, month_num INT64,
  quarter STRING, anime_season STRING
);

CREATE OR REPLACE TABLE `your-project.anime_dw.fact_sales_series` (
  id INT64 NOT NULL, media_key INT64 NOT NULL, title STRING NOT NULL, jp_title STRING,
  period_type STRING, raw_period INT64, volume INT64, sales INT64,  -- volume/sales: not in CSV, stay NULL
  anime_id INT64, score NUMERIC, members INT64, favourites INT64, scored_by INT64,  -- EXT: engagement measures
  aired_start DATE, aired_end DATE                                                   -- EXT
);

-- SCD Type 2 tables that power the lifecycle analysis (EXT)
CREATE OR REPLACE TABLE `your-project.anime_dw.dim_anime_status_scd2` (
  status_sk INT64 NOT NULL, anime_id INT64 NOT NULL, status STRING NOT NULL,
  valid_from DATE, valid_to DATE, is_current BOOL
);

CREATE OR REPLACE TABLE `your-project.anime_dw.dim_studio_tier_scd2` (
  tier_sk INT64 NOT NULL, studio_name STRING NOT NULL, tier STRING NOT NULL, tier_rank INT64 NOT NULL,
  valid_from_year INT64 NOT NULL, valid_to_year INT64 NOT NULL, is_current BOOL
);
