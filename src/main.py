from dotenv import load_dotenv
from adaptation_greenlight import DataViz
from bq_client import Bq
from logger import PipelineLogger

load_dotenv()
log = PipelineLogger.get_logger()

log.info("Starting Anime2026 warehouse & visualization pipeline")
client = Bq("anime_dw")

# client.load_staging_data()
# client.init_star_schema()
# client.transform_data()

data_viz = DataViz(client)
data_viz.visualize_top_10()
data_viz.visualize_halo()
log.info("Pipeline completed successfully")
