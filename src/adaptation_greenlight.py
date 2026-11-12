import re
import numpy as np
import pandas as pd
from bq_client import Bq
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import train_test_split,cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import make_pipeline

class DataViz:
    def __init__(self, client):
        self.__client = client
        self.model = None
        self.features = ["log_before","is_shounen"]

    def fetch_dataset(self,sql_path: str) -> pd.DataFrame:
        sql = self.__client.read_sql(sql_path)

        return sql.to_dataframe()

    def prepare_data(self,df: pd.DataFrame):
        df = self.fetch_dataset("../sql/adaptation_greenlight.sql")
        train_df = df[(df["is_adapted"] == True)
        & (df["sales_before_anime"] > 0)
        & (df["sales_after_anime"] > 0)
        ].copy()


