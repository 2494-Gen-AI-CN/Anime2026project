import logging

from dotenv import load_dotenv
from google.cloud import bigquery
from bq_client import Bq as client

load_dotenv()

client = client("anime_dw")

client.load_staging_data()

client.transform_data()




log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

