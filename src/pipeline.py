import os
import pathlib

from dotenv import load_dotenv
from google.cloud import bigquery
from pathlib import Path
import logging as log
load_dotenv()

cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
class Client:
    def __init__(self,dataset : str, location : str | None = "northamerica-northeast2"):
        self.__bq_client = bigquery.Client()
        self.__data_path = Path("../data")
        self.__dataset_id = dataset or "anime_dw"
        self.__location = location
        self.logger = log.getLogger(__name__)
        # self.logger.setLevel(level=log.INFO)
        self.logger.info('Initializing BigQuery client')

        self.dataset_ref = f"{self.__bq_client.project}.{self.__dataset_id}"
        self.__bq_client.create_dataset(self.dataset_ref, exists_ok=True)
    def get_client(self):
        return self.__bq_client

    @staticmethod
    def table_name_from_path(file_path: Path) -> str:
        return file_path.stem.replace("-","_").replace(" ","_")

    def load_staging_data(self):

        for file_path in sorted(self.__data_path.glob("**/*.*")):
            loaded_tables: dict[str, Path] = {}
            config = None
            match file_path.suffix.lower():
                case ".csv":
                    config = bigquery.LoadJobConfig(
                        source_format=bigquery.SourceFormat.CSV,
                        skip_leading_rows=1,
                        autodetect=True,
                        allow_quoted_newlines=True,
                        column_name_character_map="V2",
                    )
                case ".parquet" | ".pq":
                    config = bigquery.LoadJobConfig(
                        source_format=bigquery.SourceFormat.PARQUET,
                        skip_leading_rows=1,
                        autodetect=True,
                        allow_quoted_newlines=True,
                        column_name_character_map="V2",
                    )
                case ".json" | ".jsonl" | ".ndjson":
                    config = bigquery.LoadJobConfig(
                        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                        skip_leading_rows=1,
                        autodetect=True,
                        allow_quoted_newlines=True,
                        column_name_character_map="V2",
                    )
                case _:
                    print("Unsupported File Format")
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
            sql = f.read().format(project_id=self.__bq_client.project, dataset=self.__dataset_id)
        job = self.__bq_client.query(sql, location=self.__location)
        job.result()
        self.logger.info(f"Finished Executing {file_path}")
        return job

