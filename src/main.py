import logging

from dotenv import load_dotenv
from google.cloud import bigquery
from adaptation_greenlight import DataViz
from bq_client import Bq as client

load_dotenv()

client = client("anime_dw")

# client.load_staging_data()
# client.init_star_schema()
# client.transform_data()

data_viz = DataViz(client)
data_viz.visualize()


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

