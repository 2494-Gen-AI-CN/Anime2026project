import re
import numpy as np
import pandas as pd
from pipeline import Client
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



