"""Clean manga_dataset.csv and load it into BigQuery.

Run:  python load_manga_to_bigquery.py
"""
import pandas as pd
from google.cloud import bigquery

# ---- EDIT THESE ----
PROJECT_ID = "desk-davidluu"
CSV_PATH = "./data/manga_dataset.csv"      # path to the CSV on your machine
DATASET = "manga_dataset"
TABLE = "manga"                     # table name inside the dataset
LOCATION = "northamerica-northeast2"# dataset location, only used if the dataset is created
# --------------------

# 1. Read the CSV. pandas handles the multi-line synopsis cells that break BigQuery's CSV loader.
df = pd.read_csv(CSV_PATH)
print(f"Read {len(df):,} rows")

# 2. Drop exact duplicate rows (the file has 260).
df = df.drop_duplicates()
print(f"{len(df):,} rows after dropping duplicates")

# 3. Fix types. chapters/volumes are whole numbers but were stored as floats because of blanks.
for col in ["chapters", "volumes"]:
    df[col] = df[col].astype("Int64")

for col in ["published_from", "published_to"]:
    df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

# 4. Create the dataset if it does not exist.
client = bigquery.Client(project=PROJECT_ID)
dataset = bigquery.Dataset(f"{PROJECT_ID}.{DATASET}")
dataset.location = LOCATION
client.create_dataset(dataset, exists_ok=True)

# 5. Load the dataframe (sent as Parquet, so newlines in text are not a problem).
schema = [
    bigquery.SchemaField("mal_id", "INTEGER"),
    bigquery.SchemaField("title", "STRING"),
    bigquery.SchemaField("title_english", "STRING"),
    bigquery.SchemaField("title_japanese", "STRING"),
    bigquery.SchemaField("type", "STRING"),
    bigquery.SchemaField("chapters", "INTEGER"),
    bigquery.SchemaField("volumes", "INTEGER"),
    bigquery.SchemaField("status", "STRING"),
    bigquery.SchemaField("publishing", "BOOLEAN"),
    bigquery.SchemaField("published_from", "DATE"),
    bigquery.SchemaField("published_to", "DATE"),
    bigquery.SchemaField("score", "FLOAT"),
    bigquery.SchemaField("scored_by", "INTEGER"),
    bigquery.SchemaField("rank", "INTEGER"),
    bigquery.SchemaField("popularity", "INTEGER"),
    bigquery.SchemaField("members", "INTEGER"),
    bigquery.SchemaField("favorites", "INTEGER"),
    bigquery.SchemaField("authors", "STRING"),
    bigquery.SchemaField("serializations", "STRING"),
    bigquery.SchemaField("genres", "STRING"),
    bigquery.SchemaField("themes", "STRING"),
    bigquery.SchemaField("demographics", "STRING"),
    bigquery.SchemaField("synopsis", "STRING"),
    bigquery.SchemaField("image_url", "STRING"),
]
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
