"""Train a model on manga that already got an anime, then project Kagurabachi's growth.

Growth = yearly series sales the year AFTER season 1 aired / yearly series sales the year BEFORE.
Only pre-anime information is used as features, so Kagurabachi (no anime yet) is a fair test case.

Run:  python adaptation_growth_model.py
"""
import re

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# ---- EDIT THESE ----
USE_BIGQUERY = True                    # False = read the sales and manga CSVs from this folder instead
PROJECT_ID = "desk-davidluu"
SALES_TABLE = "desk-davidluu.series_sales.sales"
MANGA_TABLE = "desk-davidluu.manga_dataset.manga"
ANIME_CSV = "./data/anime-dataset-2026.csv"   # the anime dataset CSV
SALES_CSV = "./data/series_sales.csv"         # only used when USE_BIGQUERY = False
MANGA_CSV = "./data/manga_dataset.csv"        # only used when USE_BIGQUERY = False
TARGET_TITLE = "Blue Lock"           # title as it appears in the sales table
ASSUMED_AIR_YEAR = 2027                # ASSUMPTION: the year Kagurabachi season 1 airs
# --------------------


def norm(x):
    """Lowercase and strip punctuation/spaces so titles can be matched. Keeps Japanese characters."""
    return re.sub(r"[\W_]+", "", x.lower()) if isinstance(x, str) else ""


# ---------- 1. Load the three datasets ----------
def load_sales():
    if USE_BIGQUERY:
        from google.cloud import bigquery

        client = bigquery.Client(project=PROJECT_ID)
        df = client.query(
            f"SELECT media_type, title, jp_title, period_type, period_start, sales "
            f"FROM `{SALES_TABLE}`"
        ).to_dataframe()
    else:
        df = pd.read_csv(SALES_CSV).drop_duplicates()
        monthly = df["period_type"] == "Monthly"
        start = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
        start[monthly] = pd.to_datetime(df.loc[monthly, "raw_period"], format="%b %Y")
        start[~monthly] = pd.to_datetime(df.loc[~monthly, "raw_period"] + "-01-01")
        df["period_start"] = start
    df["period_start"] = pd.to_datetime(df["period_start"])
    return df[df["media_type"] == "Manga"].copy()


def load_manga():
    cols = "title, title_english, title_japanese, published_from, demographics, members"
    if USE_BIGQUERY:
        from google.cloud import bigquery

        client = bigquery.Client(project=PROJECT_ID)
        df = client.query(f"SELECT {cols} FROM `{MANGA_TABLE}`").to_dataframe()
    else:
        df = pd.read_csv(MANGA_CSV).drop_duplicates()[[c.strip() for c in cols.split(",")]]
    df["published_from"] = pd.to_datetime(df["published_from"], errors="coerce")
    df["keys"] = df.apply(
        lambda r: {norm(r["title"]), norm(r["title_english"]), norm(r["title_japanese"])} - {""}, axis=1
    )
    return df


def load_anime():
    a = pd.read_csv(ANIME_CSV)
    a = a[a["Type"].isin(["TV", "ONA"]) & (a["Source"] == "Manga")].copy()
    a["start"] = pd.to_datetime(a["Aired"].str.split(" to ").str[0], format="%b %d, %Y", errors="coerce")
    a = a.dropna(subset=["start"])
    a["keys"] = a.apply(lambda r: {norm(r["Name"]), norm(r["English name"]), norm(r["Other name"])} - {""}, axis=1)
    return a


sales, manga, anime = load_sales(), load_manga(), load_anime()
titles = sales[["title", "jp_title"]].drop_duplicates()
print(f"Sales titles: {len(titles)} | manga rows: {len(manga):,} | manga-sourced TV/ONA anime: {len(anime):,}")

# ---------- 2. Link each sales title to its first anime air date and its manga row ----------
first_air, manga_info = {}, {}
for _, r in titles.iterrows():
    keys = {norm(r["title"]), norm(r["jp_title"])} - {""}
    a = anime[anime["keys"].map(lambda k: bool(k & keys))]
    if len(a):
        first_air[r["title"]] = a["start"].min()
    m = manga[manga["keys"].map(lambda k: bool(k & keys))]
    if len(m):
        manga_info[r["title"]] = m.sort_values("members", ascending=False).iloc[0]
print(f"Titles matched to an anime: {len(first_air)} | matched to a manga row: {len(manga_info)}")

# ---------- 3. Yearly series totals (one value per title per year) ----------
yearly = sales[(sales["period_type"] == "Yearly")].copy()
yearly["year"] = yearly["period_start"].dt.year
yearly_tbl = yearly.pivot_table(index="title", columns="year", values="sales", aggfunc="max")


def manga_features(title, air_year):
    """Features known BEFORE the anime: manga age at air time and demographic."""
    row = manga_info.get(title)
    if row is None:
        return np.nan, 0
    age = air_year - row["published_from"].year if pd.notna(row["published_from"]) else np.nan
    shounen = int(isinstance(row["demographics"], str) and "Shounen" in row["demographics"])
    return age, shounen


# ---------- 4. Build the training set ----------
rows = []
for title, air in first_air.items():
    y = air.year
    if title in yearly_tbl.index and (y - 1) in yearly_tbl.columns and (y + 1) in yearly_tbl.columns:
        before, after = yearly_tbl.loc[title, y - 1], yearly_tbl.loc[title, y + 1]
        if pd.notna(before) and pd.notna(after) and before > 0:
            age, shounen = manga_features(title, y)
            rows.append(
                dict(title=title, air_year=y, before=before, after=after,
                     log_before=np.log(before), manga_age=age, is_shounen=shounen,
                     log_growth=np.log(after / before))
            )
train = pd.DataFrame(rows).sort_values("air_year")
train["manga_age"] = train["manga_age"].clip(lower=0).fillna(train["manga_age"].median())
print(f"\nTraining titles (sales known the year before AND the year after season 1): {len(train)}")
print(f"Median growth: {np.exp(train['log_growth'].median()):.2f}x | "
      f"range: {np.exp(train['log_growth'].min()):.2f}x to {np.exp(train['log_growth'].max()):.1f}x")

FEATURES = ["log_before", "manga_age", "is_shounen"]
X, y = train[FEATURES], train["log_growth"]

# ---------- 5. Train and check with leave-one-out ----------
models = {
    "Median (no model)": DummyRegressor(strategy="median"),
    "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=3.0)),
    "RandomForest": RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=42),
}
print("\nLeave-one-out check (each title is predicted by a model that never saw it):")
loo_resid = {}
for name, model in models.items():
    pred = cross_val_predict(model, X, y, cv=LeaveOneOut())
    loo_resid[name] = y - pred
    print(f"  {name}: typical error {np.median(np.abs(loo_resid[name])):.2f} (log scale)")
best = min(models, key=lambda n: np.median(np.abs(loo_resid[n])))
print(f"  -> using: {best}")
if best != "Ridge" and best != "RandomForest":
    print("  (neither model beat just guessing the typical growth, so the features add no proven value yet)")
model = models[best].fit(X, y)

# ---------- 6. Apply to the target series ----------
t = sales[(sales["title"] == TARGET_TITLE)]
monthly_total = t[(t["period_type"] == "Monthly")].sort_values("period_start")
latest = t["period_start"].max()
last12 = monthly_total[monthly_total["period_start"] > latest - pd.DateOffset(months=12)]
yearly_target = yearly_tbl.loc[TARGET_TITLE].dropna() if TARGET_TITLE in yearly_tbl.index else pd.Series(dtype=float)

baselines = {}
if len(last12):
    baselines[f"sum of monthly series totals in the 12 months to {latest:%b %Y} "
              f"({len(last12)} months have data, so this is a lower bound)"] = last12["sales"].sum()
if len(yearly_target):
    baselines[f"latest yearly series total ({yearly_target.index[-1]})"] = yearly_target.iloc[-1]

age, shounen = manga_features(TARGET_TITLE, ASSUMED_AIR_YEAR)
age = 0 if pd.isna(age) else max(age, 0)
lo, hi = np.percentile(loo_resid[best], [10, 90])
print(f"\n{TARGET_TITLE}: assumed season 1 year {ASSUMED_AIR_YEAR} -> manga age {age:.0f}, shounen={shounen}")
for label, base in baselines.items():
    pt = model.predict(pd.DataFrame([dict(log_before=np.log(base), manga_age=age, is_shounen=shounen)]))[0]
    print(f"  Baseline = {label}: {base:,.0f}")
    print(f"    projected growth {np.exp(pt):.2f}x (likely range {np.exp(pt + lo):.2f}x to {np.exp(pt + hi):.2f}x)"
          f" -> about {base * np.exp(pt):,.0f} sales in the year after season 1")
