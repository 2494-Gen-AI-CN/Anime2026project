from datetime import datetime, timezone
import hashlib
import io
import os
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery
import pandas as pd

from logger import PipelineLogger

load_dotenv()

cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
PROJECT_ROOT = Path(__file__).resolve().parent.parent

KEY_COLUMNS = {
    "anime_dataset_2026": ["anime_id"],
    "manga_dataset": ["mal_id"],
    "series_sales": ["title", "media_type", "period_type", "raw_period", "volume"],
    "series_sales_v2": ["title", "media_type", "period_type", "raw_period", "volume"],
}


def clean_and_split_rejects(
    df: pd.DataFrame,
    table_name: str,
    source_file: str,
    ran_at: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop rows with blank keys or duplicate keys, returning (clean_df, rejects_df)."""
    keys = [c for c in KEY_COLUMNS.get(table_name, []) if c in df.columns]
    reject_parts = []

    work = df.copy()
    for col in work.columns:
        if work[col].dtype == object or pd.api.types.is_string_dtype(work[col]):
            work[col] = work[col].astype(str).str.strip()

    # Reject rows missing key values
    if keys:
        blank_mask = work[keys].eq("").any(axis=1)
        if blank_mask.any():
            bad = work[blank_mask].copy()
            bad["reject_reason"] = f"Missing required key in {keys}"
            reject_parts.append(bad)
            work = work[~blank_mask]

    # Reject non-numeric sales on sales tables
    if "sales" in work.columns:
        sales_num = pd.to_numeric(work["sales"], errors="coerce")
        bad_sales = sales_num.isna() | (sales_num < 0)
        if bad_sales.any():
            bad = work[bad_sales].copy()
            bad["reject_reason"] = "Invalid or negative 'sales'"
            reject_parts.append(bad)
            work = work[~bad_sales]
        # Keep highest sales row when duplicate keys exist
        work = work.assign(_s=pd.to_numeric(work["sales"])).sort_values("_s", ascending=False).drop(columns="_s")

    # Reject duplicate keys (or exact duplicate rows if no keys defined)
    dup_mask = work.duplicated(subset=keys or None, keep="first")
    if dup_mask.any():
        bad = work[dup_mask].copy()
        bad["reject_reason"] = f"Duplicate record on ({', '.join(keys)})" if keys else "Duplicate row"
        reject_parts.append(bad)
        work = work[~dup_mask]

    if reject_parts:
        rejects = pd.concat(reject_parts, ignore_index=True)
        rejects.insert(0, "rejected_at", ran_at)
        rejects.insert(1, "source_file", source_file)
        rejects.insert(2, "table_name", table_name)
    else:
        rejects = pd.DataFrame(columns=["rejected_at", "source_file", "table_name", "reject_reason"])

    return work.reset_index(drop=True), rejects


class Bq:
    def __init__(self, dataset: str | None, location: str | None = None):
        self.__location = location or "northamerica-northeast2"
        self.__bq_client = bigquery.Client(location=self.__location)  # default for every job
        self.__data_path = Path("../data")
        self.__staging_dataset = "anime_staging"
        self.__dataset_id = dataset or "anime_dw"
        self.logger = log.getLogger(__name__)
        self.logger.info("Initializing BigQuery client")

        self._ensure_dataset(self.__staging_dataset)
        self._ensure_dataset(self.__dataset_id)

    def _ensure_dataset(self, dataset_id: str):
        ds = bigquery.Dataset(f"{self.__bq_client.project}.{dataset_id}")
        ds.location = self.__location
        return self.__bq_client.create_dataset(ds, exists_ok=True)
    def __init__(self, dataset: str | None = None, location: str | None = "US"):
        self.logger = PipelineLogger.get_logger()
        self.__bq_client = bigquery.Client()
        self.__data_path = Path("../data") if Path("../data").exists() else PROJECT_ROOT / "data"
        self.__log_dir = Path("../logs") if Path("../logs").exists() else PROJECT_ROOT / "logs"
        self.__log_dir.mkdir(parents=True, exist_ok=True)
        self.__load_log_csv = self.__log_dir / "load_log.csv"
        self.__rejects_csv = self.__log_dir / "rejects.csv"
        self.__staging_dataset = "anime_staging"
        self.__dataset_id = dataset or "anime_dw"
        self.__location = location

        self.logger.info("Initializing BigQuery client (project=%s, dataset=%s)", self.__bq_client.project, self.__dataset_id)
        self.dataset_ref = f"{self.__bq_client.project}.{self.__staging_dataset}"
        self.__bq_client.create_dataset(self.dataset_ref, exists_ok=True)

    def get_client(self):
        return self.__bq_client

    @staticmethod
    def table_name_from_path(file_path: Path) -> str:
        return file_path.stem.replace("-", "_").replace(" ", "_")

    def _already_loaded(self, table_name: str, file_hash: str) -> bool:
        if not self.__load_log_csv.exists():
            return False
        log_df = pd.read_csv(self.__load_log_csv, dtype=str)
        return not log_df[
            (log_df["table_name"] == table_name)
            & (log_df["file_hash"] == file_hash)
            & (log_df["status"] == "LOADED")
        ].empty

    def _write_df_to_bq(self, df: pd.DataFrame, table_name: str, write_disposition: str):
        table_ref = f"{self.__bq_client.project}.{self.__staging_dataset}.{table_name}"
        buf = io.BytesIO(df.to_csv(index=False).encode("utf-8"))
        config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            autodetect=True,
            allow_quoted_newlines=True,
            column_name_character_map="V2",
            write_disposition=write_disposition,
        )
        self.__bq_client.load_table_from_file(buf, table_ref, job_config=config).result()

    def _append_load_log(self, entry: dict):
        entry_df = pd.DataFrame([entry])
        entry_df.to_csv(self.__load_log_csv, mode="a", header=not self.__load_log_csv.exists(), index=False)
        self._write_df_to_bq(entry_df, "load_log", bigquery.WriteDisposition.WRITE_APPEND)

    def load_staging_data(self) -> list[dict]:
        ran_at = datetime.now(timezone.utc).isoformat()
        logs = []

        for file_path in sorted(self.__data_path.glob("**/*.*")):
            suffix = file_path.suffix.lower()
            if suffix not in {".csv", ".parquet", ".pq", ".json", ".jsonl", ".ndjson"}:
                self.logger.warning("Unsupported file format: %s", file_path.name)
                continue

            table_name = self.table_name_from_path(file_path)
            table_ref = f"{self.__bq_client.project}.anime_staging.{table_name}"
            with file_path.open("rb") as f:
                job = self.__bq_client.load_table_from_file(f, table_ref, job_config=config)
                job.result()
            loaded_tables[table_name] = file_path
        return None

    def read_sql(self,file_path : str):
        with open(file_path, "r", encoding="utf-8") as f:
            file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]

            if self._already_loaded(table_name, file_hash):
                entry = {
                    "ran_at": ran_at,
                    "source_file": file_path.name,
                    "table_name": table_name,
                    "file_hash": file_hash,
                    "rows_read": 0,
                    "rows_loaded": 0,
                    "rows_rejected": 0,
                    "status": "SKIPPED_ALREADY_LOADED",
                }
                self._append_load_log(entry)
                logs.append(entry)
                self.logger.info("Skipped %s (already loaded)", file_path.name)
                continue

            raw_df = (
                pd.read_csv(file_path, dtype=str, keep_default_na=False)
                if suffix == ".csv"
                else pd.read_parquet(file_path)
                if suffix in (".parquet", ".pq")
                else pd.read_json(file_path, lines=suffix in (".jsonl", ".ndjson"))
            )
            clean_df, rejects_df = clean_and_split_rejects(raw_df, table_name, file_path.name, ran_at)

            self._write_df_to_bq(clean_df, table_name, bigquery.WriteDisposition.WRITE_TRUNCATE)
            if not rejects_df.empty:
                rejects_df.to_csv(self.__rejects_csv, mode="a", header=not self.__rejects_csv.exists(), index=False)
                self._write_df_to_bq(rejects_df[["rejected_at", "source_file", "table_name", "reject_reason"]], "rejects", bigquery.WriteDisposition.WRITE_APPEND)

            entry = {
                "ran_at": ran_at,
                "source_file": file_path.name,
                "table_name": table_name,
                "file_hash": file_hash,
                "rows_read": len(raw_df),
                "rows_loaded": len(clean_df),
                "rows_rejected": len(rejects_df),
                "status": "LOADED",
            }
            self._append_load_log(entry)
            logs.append(entry)
            self.logger.info("Loaded %s (read=%d, loaded=%d, rejected=%d)", file_path.name, len(raw_df), len(clean_df), len(rejects_df))

        return logs

    def read_sql(self, file_path: str):
        path_obj = Path(file_path)
        if not path_obj.exists():
            path_obj = (PROJECT_ROOT / "src" / file_path).resolve()
        with open(path_obj, "r", encoding="utf-8") as f:
            sql = f.read().format(project_id=self.__bq_client.project, dataset=self.__dataset_id)
        job = self.__bq_client.query(sql, location=self.__location)
        job.result()
        self.logger.info("Finished executing %s", path_obj.name)
        return job

    def init_star_schema(self):
        star_dataset = f"{self.__bq_client.project}.{self.__dataset_id}"
        self.__bq_client.create_dataset(star_dataset, exists_ok=True)
        self.read_sql("../sql/create_star_schema.sql")

    def transform_data(self):
        self.read_sql("../sql/transform.sql")

    def init_star_schema(self):
        star_dataset = f"{self.__bq_client.project}.{self.__dataset_id}"
        self.__bq_client.create_dataset(star_dataset, exists_ok=True)
        self.read_sql("../sql/create_star_schema.sql")    


