from pathlib import Path
from unittest.mock import patch
from google.cloud import bigquery
from db import Client


def test_table_name_from_path():
    """Verify hyphens and spaces in filenames are converted to underscores."""
    path = Path("data/anime-dataset 2026.csv")
    assert Client.table_name_from_path(path) == "anime_dataset_2026"


@patch("db.bigquery.Client")
def test_extract_data_loads_supported_formats(mock_bq_class, tmp_path):
    """
    Verify void extract_data() method:
    - Calls BigQuery load_table_from_file for .csv, .parquet, and .jsonl
    - Names each table after its filename
    - Skips unsupported files (.txt)
    """
    # --- 1. ARRANGE ---
    (tmp_path / "anime-2026.csv").write_text("id,name\n1,Naruto\n", encoding="utf-8")
    (tmp_path / "studios.parquet").write_bytes(b"fake parquet bytes")
    (tmp_path / "reviews.jsonl").write_text('{"id": 1}\n', encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")

    # Configure the mocked bigquery.Client() instance
    mock_bq = mock_bq_class.return_value
    mock_bq.project = "my_test_project"

    db_client = Client(dataset_id="my_dataset")
    # Point the private __data_path to pytest's temporary folder for this test
    db_client._Client__data_path = tmp_path

    # --- 2. ACT (void function, returns None) ---
    db_client.extract_data()

    # --- 3. ASSERT ---
    # Only the 3 valid files should be uploaded (notes.txt skipped)
    assert mock_bq.load_table_from_file.call_count == 3

    calls = mock_bq.load_table_from_file.call_args_list

    # Call 1: anime-2026.csv
    assert calls[0].args[1] == "my_test_project.my_dataset.anime_2026"
    assert calls[0].kwargs["job_config"].source_format == bigquery.SourceFormat.CSV

    # Call 2: reviews.jsonl
    assert calls[1].args[1] == "my_test_project.my_dataset.reviews"
    assert calls[1].kwargs["job_config"].source_format == bigquery.SourceFormat.NEWLINE_DELIMITED_JSON

    # Call 3: studios.parquet
    assert calls[2].args[1] == "my_test_project.my_dataset.studios"
    assert calls[2].kwargs["job_config"].source_format == bigquery.SourceFormat.PARQUET
