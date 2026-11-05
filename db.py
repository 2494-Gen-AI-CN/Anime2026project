import os
from dotenv import load_dotenv
from google.cloud import bigquery
from pathlib import Path
from logger import Logger
load_dotenv()

cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
class Client:
    def __init__(self, dataset_id: str | None = None):
        self.logger = Logger()
        self.__client = bigquery.Client()
        self.__data_path = Path("./data")
        self.__dataset_id = dataset_id or os.getenv("BIGQUERY_DATASET","anime_dataset")
        self.logger.info('Initializing BigQuery client')

        self.dataset_ref = f"{self.__client.project}.{self.__dataset_id}"
        self.__client.create_dataset(self.dataset_ref,exists_ok=True)
    def get_client(self):
        return self.__client

    @staticmethod
    def table_name_from_path(file_path: Path) -> str:
        return file_path.stem.replace("-","_").replace(" ","_")

    def extract_data(self):

        for file_path in sorted(self.__data_path.glob("**/*.*")):
            loaded_tables: dict[str, Path] = {}
            config = None
            match file_path.suffix.lower():
                case ".csv":
                    config = bigquery.LoadJobConfig(
                        source_format=bigquery.SourceFormat.CSV,
                        skip_leading_rows=1,
                        autodetect=True,
                    )
                case ".parquet" | ".pq":
                    config = bigquery.LoadJobConfig(
                        source_format=bigquery.SourceFormat.PARQUET,
                        skip_leading_rows=1,
                        autodetect=True
                    )
                case ".json" | ".jsonl" | ".ndjson":
                    config = bigquery.LoadJobConfig(
                        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                        skip_leading_rows=1,
                        autodetect=True,
                    )
                case _:
                    print("Unsupported File Format")
                    continue

            table_name = self.table_name_from_path(file_path)
            table_ref = f"{self.__client.project}.{self.__dataset_id}.{table_name}"
            with file_path.open("rb") as f:
                job = self.__client.load_table_from_file(f, table_ref, job_config=config)
                job.result()
            loaded_tables[table_name] = file_path
        return None

    # def write_csv(self,rows,path):
    #     with open(path, 'w', newline='', endcoding="utf-8") as f:
    #         writer = csv.DictWriter(f,fieldnames=rows[0])
    #         writer.writeheader()
    #         writer.writerows(rows)





