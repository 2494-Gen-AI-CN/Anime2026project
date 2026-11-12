import logging

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

client = bigquery.Client()

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)