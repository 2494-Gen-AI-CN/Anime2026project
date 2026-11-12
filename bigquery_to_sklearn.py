"""Pull the manga + sales join from BigQuery into pandas, then fit a scikit-learn model.

Run:  python bigquery_to_sklearn.py
"""
import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline

PROJECT_ID = "desk-davidluu"

QUERY = """
WITH sales_totals AS (
  SELECT title, period_start, sales
  FROM `desk-davidluu.series_sales.sales`
  WHERE period_type = 'Yearly'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY title ORDER BY period_start DESC) = 1
)
SELECT
  m.title,
  m.score,
  m.popularity,
  m.rank,
  SUM(m.members) AS total_members,
  SUM(m.favorites) AS total_favorites,
  SUM(s.sales) AS total_sales,
  MAX(s.period_start) AS sales_as_of
FROM `desk-davidluu.manga_dataset.manga` AS m
JOIN sales_totals AS s
  ON LOWER(TRIM(m.title_english)) = LOWER(TRIM(s.title))
WHERE EXTRACT(YEAR FROM s.period_start) = 2025
GROUP BY m.title, m.score, m.popularity, m.rank
ORDER BY total_sales DESC, m.rank, m.popularity DESC
"""

# 1. Run the query and get the result as a pandas DataFrame.
client = bigquery.Client(project=PROJECT_ID)
df = client.query(QUERY).to_dataframe()
print(f"Got {len(df):,} rows")
print(df.head())

# 2. Pick features (X) and the thing to predict (y).
FEATURES = ["score", "popularity", "rank", "total_members", "total_favorites"]
df = df.dropna(subset=["total_sales"])
X = df[FEATURES].astype(float)
y = np.log1p(df["total_sales"])  # sales are very skewed, so predict the log

# 3. Split into training and test sets.
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 4. Fill missing values with the median, then fit a random forest.
model = make_pipeline(
    SimpleImputer(strategy="median"),
    RandomForestRegressor(n_estimators=300, random_state=42),
)
model.fit(X_train, y_train)

# 5. Evaluate on the test set.
pred = model.predict(X_test)
print(f"R^2: {r2_score(y_test, pred):.3f}")
print(f"MAE (log scale): {mean_absolute_error(y_test, pred):.3f}")

# 6. Which features mattered most?
importances = pd.Series(model[-1].feature_importances_, index=FEATURES).sort_values(ascending=False)
print(importances)
