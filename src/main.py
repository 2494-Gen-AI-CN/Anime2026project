import logging

from dotenv import load_dotenv

from bq_client import Bq
from etl_and_analysis import run_pipeline
from plot_lifecycle import make_plot
from q2_audience_retention import main as run_q2_pipeline   # CSV -> BigQuery -> Q2 results
from plot_q2 import main as make_q2_plots                   # Q2 charts

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# The lifecycle tables (incl. the SCD2 ones) are written to the same dataset as your Bq class.
# Leave False until you've checked they won't overwrite tables created by init_star_schema().
LOAD_LIFECYCLE_TABLES_TO_BQ = False

# Question 2 (Audience Hype vs. Actual Retention) can be switched off while you work on the others.
RUN_Q2 = True


def main():
    bq = Bq("anime_dw")

    bq.load_staging_data()
    bq.transform_data()
    bq.init_star_schema()

    project = bq.get_client().project if LOAD_LIFECYCLE_TABLES_TO_BQ else None
    results = run_pipeline(bq_project=project)      # builds tables + prints the lifecycle analysis
    log.info("Lifecycle tables built: %s", ", ".join(k for k in results if k != "raw"))

    make_plot(results["raw"], show=True)            # saves outputs/lifecycle_scatter.png and opens it

    if RUN_Q2:
        log.info("Running Question 2: audience hype vs. retention")
        run_q2_pipeline()                           # writes CSVs + charts to src/output
        make_q2_plots(show=True)                    # saves 3 PNGs to src/output and opens them


if __name__ == "__main__":
    main()