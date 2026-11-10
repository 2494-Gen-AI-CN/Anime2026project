"""Clean series_sales.csv and load it into a NEW BigQuery dataset.

Run:  python load_series_sales_to_bigquery.py
"""
import pandas as pd
from google.cloud import bigquery

# ---- EDIT THESE ----
PROJECT_ID = "desk-davidluu"
CSV_PATH = "./data/series_sales.csv"       # path to the CSV on your machine
DATASET = "series_sales"            # new dataset to create (use "manga_dataset" to reuse your old one)
TABLE = "sales"                     # table name inside the dataset
LOCATION = "northamerica-northeast2"# dataset location, only used when the dataset is created
# --------------------

# 1. Read the CSV.
df = pd.read_csv(CSV_PATH)
print(f"Read {len(df):,} rows")

# 2. Drop exact duplicate rows (the file has 519).
df = df.drop_duplicates()
print(f"{len(df):,} rows after dropping duplicates")

# 3. Rename "index" to row_id so it is not confused with SQL keywords.
df = df.rename(columns={"index": "row_id"})

# 4. Turn raw_period into a real date.
#    Monthly rows look like "Oct 2009" -> 2009-10-01. Yearly rows look like "2009" -> 2009-01-01.
monthly = df["period_type"] == "Monthly"
df["period_start"] = pd.NaT
df.loc[monthly, "period_start"] = pd.to_datetime(
    df.loc[monthly, "raw_period"], format="%b %Y"
)
df.loc[~monthly, "period_start"] = pd.to_datetime(
    df.loc[~monthly, "raw_period"] + "-01-01", format="%Y-%m-%d"
)
df["period_start"] = pd.to_datetime(df["period_start"]).dt.date

# 5. The volume column mixes numbers with the text "Series total", so split it in two.
df["is_series_total"] = df["volume"] == "Series total"
df["volume_number"] = pd.to_numeric(df["volume"], errors="coerce").astype("Int64")
df = df.drop(columns="volume")

# 6. Create the dataset (does nothing if it already exists).
client = bigquery.Client(project=PROJECT_ID)
dataset = bigquery.Dataset(f"{PROJECT_ID}.{DATASET}")
dataset.location = LOCATION
client.create_dataset(dataset, exists_ok=True)

# 7. Load the table.
schema = [
    bigquery.SchemaField("row_id", "INTEGER"),
    bigquery.SchemaField("media_type", "STRING"),
    bigquery.SchemaField("title", "STRING"),
    bigquery.SchemaField("jp_title", "STRING"),
    bigquery.SchemaField("period_type", "STRING"),
    bigquery.SchemaField("raw_period", "STRING"),
    bigquery.SchemaField("sales", "INTEGER"),
    bigquery.SchemaField("period_start", "DATE"),
    bigquery.SchemaField("is_series_total", "BOOLEAN"),
    bigquery.SchemaField("volume_number", "INTEGER"),
]
df = df[[f.name for f in schema]]  # put columns in schema order

job_config = bigquery.LoadJobConfig(
    schema=schema,
    write_disposition="WRITE_TRUNCATE",  # re-running replaces the table instead of duplicating rows
)
job = client.load_table_from_dataframe(
    df, f"{PROJECT_ID}.{DATASET}.{TABLE}", job_config=job_config
)
job.result()

table = client.get_table(f"{PROJECT_ID}.{DATASET}.{TABLE}")
print(f"Loaded {table.num_rows:,} rows into {PROJECT_ID}.{DATASET}.{TABLE}")
