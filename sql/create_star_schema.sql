CREATE SCHEMA IF NOT EXISTS `{project_id}.{dataset}`;

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.dim_anime`(
    anime_id INT64 NOT NULL,
    title STRING NOT NULL,
    en_title STRING NOT NULL,
    jp_title STRING,
    score NUMERIC(4,2),
    genres ARRAY<STRING>,
    synopsis STRING,
    type STRING,
    episodes INT64,
    aired STRING,
    premiered STRING,
    status STRING,
    producers ARRAY<STRING>,
    licensors ARRAY<STRING>,
    studios ARRAY<STRING>,
    source STRING,
    duration STRING,
    rating STRING,
    rank INT64 NOT NULL,
    popularity INT64 NOT NULL,
    favourites INT64,
    scored_by INT64,
    members INT64
);

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.dim_studio_publisher` (
    org_id INT64 NOT NULL,
    title STRING NOT NULL,
    studio_name STRING NOT NULL,
    publisher_name STRING,
    magazine_name STRING
);

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.dim_author` (
    author_id INT64 NOT NULL,
    title STRING,
    author_name STRING NOT NULL,
    role STRING
);

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.dim_media_format` (
    media_key INT64 NOT NULL,
    media_type STRING NOT NULL
);

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.dim_date_period`(
    period_key INT64 NOT NULL,
    period_type STRING,
    year INT64,
    month_num INT64,
    quarter STRING,
    anime_season STRING
);

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.dim_genre`(
    genre_id INT64 NOT NULL,
    title STRING NOT NULL,
    genre_name STRING,
    demographic STRING
);

CREATE TABLE IF NOT EXISTS `{project_id}.{dataset}.fact_sales_series`(
    id INT64 NOT NULL,
    media_key INT64 NOT NULL,
    title STRING NOT NULL,
    en_title STRING,
    jp_title STRING,
    period_type STRING,
    raw_period INT64 NOT NULL,
    volume INT64,
    sales INT64
)
CLUSTER BY title, media_key, raw_period;
