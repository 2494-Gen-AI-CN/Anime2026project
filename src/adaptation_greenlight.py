import numpy as np
import pandas as pd
from numpy import median
import matplotlib.pyplot as plt
from bq_client import Bq
from sklearn.dummy import DummyRegressor
from sklearn.model_selection import train_test_split,cross_val_predict,LeaveOneOut
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import make_pipeline

class DataViz:
    def __init__(self, client):
        self.__client = client
        self.model = None
        self.features = ["log_before","is_shounen"]
        self.train_df,self.candidate_df =self.prepare_data()

    def fetch_dataset(self,sql_path: str) -> pd.DataFrame:
        sql = self.__client.read_sql(sql_path)
        return sql.to_dataframe()

    def prepare_data(self):
        df = self.fetch_dataset("../sql/adaptation_greenlight.sql")
        train_df = df[(df["is_adapted"] == True)
            & (df["sales_before_anime"] > 0)
            & (df["sales_after_anime"] > 0)
        ].copy()
        train_df["log_before"] = np.log(train_df["sales_before_anime"])
        train_df["log_growth"] = np.log(train_df["sales_after_anime"] / train_df["sales_before_anime"])
        candidate_df = df[(df["is_adapted"] == False)
        & (df["latest_baseline_sales"] > 0)
        ].copy()

        candidate_df["log_before"] = np.log(candidate_df["latest_baseline_sales"])

        return train_df,candidate_df

    def train_model(self):
        X = self.train_df[self.features]
        y = self.train_df["log_growth"]

        models = {
            "Median": DummyRegressor(strategy="median"),
            "Ridge": make_pipeline(StandardScaler(),Ridge(alpha=3.0)),
            "RandomForest": RandomForestRegressor(n_estimators=300,min_samples_leaf=3,random_state=42)
        }

        residuals = {}
        for title,candidate_model in models.items():
            preds = cross_val_predict(candidate_model,X,y,cv=5)
            residuals[title] = y - preds
            print(median(abs(residuals[title])))

        best_name = min(models, key=lambda n: np.median(np.abs(residuals[n])))
        self.loo_residuals = residuals[best_name]
        self.model = models[best_name].fit(X,y)
        return self.model

    def predict_greenlight(self):

        X_cand = self.candidate_df[self.features]
        pred_log_growth = self.model.predict(X_cand)
        low,high = np.percentile(self.loo_residuals,[10,90])
        self.candidate_df["projected_growth_x"] = np.exp(pred_log_growth)
        self.candidate_df["growth_low_x"] = np.exp(pred_log_growth + low)
        self.candidate_df["growth_high_x"] = np.exp(pred_log_growth + high)

        self.candidate_df["projected_sales"] = self.candidate_df["latest_baseline_sales"] * self.candidate_df["projected_growth_x"]
        self.candidate_df["projected_low"] = self.candidate_df["latest_baseline_sales"] * self.candidate_df["growth_low_x"]
        self.candidate_df["projected_high"] = self.candidate_df["latest_baseline_sales"] * self.candidate_df["growth_high_x"]
        self.candidate_df = self.candidate_df.sort_values("projected_sales", ascending=False)
        return self.candidate_df

    def visualize(self):
        if self.model is None:
            self.train_model()

        top10 = (
            self.predict_greenlight()
            .drop_duplicates(subset=["title"])
            .head(10)
        )

        titles = top10["title"]
        baseline = top10["latest_baseline_sales"]
        anime_boost = (top10["projected_sales"] - baseline).clip(lower=0)

        fig, ax = plt.subplots(figsize=(12, 6))

        # Bottom bar: Current Baseline Sales
        ax.bar(titles, baseline, label="Current Baseline Sales", color="#3b82f6")

        # Top stacked bar: Additional sales gained from Anime Adaptation
        ax.bar(
            titles,
            anime_boost,
            bottom=baseline,
            label="Projected Anime Boost",
            color="#f97316",
        )

        ax.set_title("Top 10 Projected Sales if Adapted")
        ax.set_ylabel("Yearly Series Sales (Yen)")
        ax.legend(loc="upper right")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.show()