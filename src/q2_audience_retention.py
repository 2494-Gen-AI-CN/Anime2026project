"""
Question 2 - Audience Hype vs. Actual Retention
    "How strongly does total audience volume correlate with viewer satisfaction scores,
     and which genres suffer the highest viewer abandonment before the season finale?"

Pipeline (run from VSCode: python q2_audience_retention.py):
  1. Load anime-dataset-2026.csv into a BigQuery staging table (all STRING columns).
  2. Build the star-schema tables dim_anime and dim_genre from staging (sql/01).
  3. Create the Q2 cohort view (sql/02) and run the three analysis queries (sql/03-05).
  4. Save result CSVs and charts to ./output.

Setup:
  pip install google-cloud-bigquery db-dtypes pandas matplotlib python-dotenv
  .env  ->  GOOGLE_APPLICATION_CREDENTIALS=credentials/<your-key>.json
"""
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

from logger import PipelineLogger

load_dotenv()
logger = PipelineLogger.get_logger()

BASE_DIR = Path(__file__).resolve().parent


def _resolve_credentials() -> None:
    """Make GOOGLE_APPLICATION_CREDENTIALS work no matter where the script is run from."""
    raw = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not raw or Path(raw).is_absolute():
        return
    # Try the path relative to the script, its parent, then the current folder.
    for root in (BASE_DIR, BASE_DIR.parent, Path.cwd()):
        candidate = (root / raw).resolve()
        if candidate.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(candidate)
            return
    raise FileNotFoundError(
        f"Could not find credentials file '{raw}'. Looked relative to {BASE_DIR}, "
        f"{BASE_DIR.parent} and {Path.cwd()}."
    )


_resolve_credentials()

# ---------------------------------------------------------------- config
PROJECT_ROOT = Path(__file__).resolve().parent.parent   # Anime2026project/ (this file lives in src/)
CSV = PROJECT_ROOT / "data" / "anime-dataset-2026.csv"
SQL_DIR = BASE_DIR.parent / "sql"
OUT_DIR = BASE_DIR / "output"
OUT_DIR.mkdir(exist_ok=True)

DATASET = "anime_q2"
LOCATION = "northamerica-northeast2"       # must match the dataset's location
STAGING_TABLE = "stg_anime_dataset"

# Staging column names follow the star-schema naming (producer, favourites, ...).
CSV_COLUMNS = [
    "anime_id", "name", "english_name", "other_name", "score", "genres", "synopsis",
    "type", "episodes", "aired", "premiered", "status", "producers", "licensors",
    "studios", "source", "duration", "rating", "rank", "popularity", "favourites",
    "scored_by", "members", "image_url",
]

client = bigquery.Client(location=LOCATION)
PROJECT = client.project


# ---------------------------------------------------------------- helpers
def _read_sql(filename: str) -> str:
    sql = (SQL_DIR / filename).read_text()
    return sql.replace("{project}", PROJECT).replace("{dataset}", DATASET)


def run_ddl(filename: str) -> None:
    """Run a .sql file that only creates tables/views (may hold several statements)."""
    logger.info("Executing DDL %s", filename)
    client.query(_read_sql(filename)).result()
    logger.info("Finished DDL %s", filename)


def run_sql(filename: str) -> pd.DataFrame:
    """Run a SELECT .sql file and return a DataFrame."""
    logger.info("Running analysis query %s", filename)
    df = client.query(_read_sql(filename)).to_dataframe()
    logger.info("Query %s returned %d rows", filename, len(df))
    return df


def ensure_dataset() -> None:
    ds = bigquery.Dataset(f"{PROJECT}.{DATASET}")
    ds.location = LOCATION
    client.create_dataset(ds, exists_ok=True)
    logger.info("Ensured BigQuery dataset %s.%s (location=%s)", PROJECT, DATASET, LOCATION)


def load_csv_to_staging() -> None:
    """Step 1: upload the raw CSV. Everything is STRING so 'UNKNOWN' values load cleanly;
    sql/01 casts to the star-schema types."""
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,                 # header row (also skips the UTF-8 BOM)
        allow_quoted_newlines=True,          # synopsis text contains line breaks
        schema=[bigquery.SchemaField(c, "STRING") for c in CSV_COLUMNS],
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    table_id = f"{PROJECT}.{DATASET}.{STAGING_TABLE}"
    with open(CSV, "rb") as f:
        client.load_table_from_file(f, table_id, job_config=job_config).result()
    row_count = client.get_table(table_id).num_rows
    logger.info("Loaded %s rows into %s", f"{row_count:,}", table_id)


# ---------------------------------------------------------------- charts
def plot_scatter_and_tiers(tiers: pd.DataFrame) -> None:
    # Pull the cohort for a scatter of hype vs satisfaction (sampled for readability).
    cohort = client.query(
        f"SELECT members, score FROM `{PROJECT}.{DATASET}.vw_q2_cohort`"
    ).to_dataframe()
    cohort["score"] = cohort["score"].astype(float)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    axes[0].scatter(cohort["members"], cohort["score"], s=6, alpha=0.3)
    axes[0].set_xscale("log")
    axes[0].set_xlabel("Audience volume (members, log scale)")
    axes[0].set_ylabel("Viewer score")
    axes[0].set_title("Bigger audiences, higher scores")

    ax2 = axes[1]
    ax2.bar(tiers["audience_tier"].astype(str), tiers["avg_abandonment"].astype(float),
            color="#c0504d")
    ax2.set_xlabel("Audience-size quintile (1 = smallest, 5 = largest)")
    ax2.set_ylabel("Avg abandonment proxy (1 - scored_by / members)")
    ax2.set_title("Abandonment falls as audience grows")
    fig.tight_layout()
    out_file = OUT_DIR / "q2_hype_vs_satisfaction.png"
    fig.savefig(out_file, dpi=150)
    logger.info("Saved chart %s", out_file)
    plt.close(fig)


def plot_genres(genres: pd.DataFrame, top_n: int = 12) -> None:
    top = genres.sort_values("size_adj_abandonment", ascending=False)
    picks = pd.concat([top.head(top_n), top.tail(top_n)]).drop_duplicates("genre_name")
    picks = picks.sort_values("size_adj_abandonment")
    colors = np.where(picks["size_adj_abandonment"].astype(float) > 0, "#c0504d", "#4f81bd")

    fig, ax = plt.subplots(figsize=(9, 8))
    ax.barh(picks["genre_name"], picks["size_adj_abandonment"].astype(float), color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Abandonment vs. same-size audiences (positive = loses more viewers)")
    ax.set_title("Size-adjusted viewer abandonment by genre (genres with 30+ titles)")
    fig.tight_layout()
    out_file = OUT_DIR / "q2_genre_abandonment.png"
    fig.savefig(out_file, dpi=150)
    logger.info("Saved chart %s", out_file)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main() -> None:
    logger.info("Starting Q2 audience retention pipeline")
    ensure_dataset()
    load_csv_to_staging()                      # 1. CSV -> staging
    run_ddl("01_build_star_schema.sql")        # 2. staging -> dim_anime, dim_genre
    run_ddl("02_q2_cohort_view.sql")           # 3. analysis cohort view

    corr = run_sql("03_q2a_correlation.sql")
    tiers = run_sql("04_q2b_audience_tiers.sql")
    genres = run_sql("05_q2c_genre_abandonment.sql")

    corr.to_csv(OUT_DIR / "q2a_correlation.csv", index=False)
    tiers.to_csv(OUT_DIR / "q2b_audience_tiers.csv", index=False)
    genres.to_csv(OUT_DIR / "q2c_genre_abandonment.csv", index=False)

    print("\n== A. Correlation: audience volume vs satisfaction ==")
    print(corr.T.to_string(header=False))
    print("\n== A2. By audience-size quintile ==")
    print(tiers.to_string(index=False))
    print("\n== B. Highest abandonment genres (raw median) ==")
    print(genres.head(10).to_string(index=False))
    print("\n== B2. Highest abandonment genres (size-adjusted) ==")
    print(genres.sort_values("size_adj_abandonment", ascending=False).head(10).to_string(index=False))

    plot_scatter_and_tiers(tiers)
    plot_genres(genres)
    logger.info("Saved Q2 CSVs and charts to %s", OUT_DIR)


if __name__ == "__main__":
    main()
