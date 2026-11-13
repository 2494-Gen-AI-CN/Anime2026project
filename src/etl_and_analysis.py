"""
Lifecycle & Status Evolution (SCD Type 2) analysis on anime-dataset-2026.csv.

  python etl_and_analysis.py                 # build star schema + run analysis locally (pandas)
  python etl_and_analysis.py --bq YOUR_PROJECT   # also load tables to BigQuery (dataset: anime_dw)

BigQuery mode needs:  pip install google-cloud-bigquery db-dtypes pyarrow
and `gcloud auth application-default login`. Then run sql/01_schema.sql (optional) and sql/02_analysis.sql.
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent   # Anime2026project/ (this file lives in src/)
CSV = PROJECT_ROOT / "data" / "anime-dataset-2026.csv"
SNAPSHOT = pd.Timestamp("2026-06-30")
FOREVER = pd.Timestamp("9999-12-31")
MIN_VOTES = 100
END_YEAR = 2026
DEMOGRAPHICS = {"Shounen", "Shoujo", "Seinen", "Josei", "Kids"}


# ---------------------------------------------------------------- extract / clean
def load_raw() -> pd.DataFrame:
    df = pd.read_csv(CSV, encoding="utf-8-sig")
    df = df.rename(columns={"Name": "name", "English name": "english_name", "Other name": "other_name",
                            "Score": "score", "Genres": "genres", "Synopsis": "synopsis", "Type": "type",
                            "Episodes": "episodes", "Aired": "aired", "Premiered": "premiered",
                            "Status": "status", "Producers": "producer", "Licensors": "licensors",
                            "Studios": "studios", "Source": "source", "Duration": "duration",
                            "Rating": "rating", "Rank": "rank", "Popularity": "popularity",
                            "Favorites": "favourites", "Scored By": "scored_by", "Members": "members"})
    for c in ["score", "episodes", "rank", "scored_by"]:          # 'UNKNOWN' -> NaN
        df[c] = pd.to_numeric(df[c], errors="coerce")
    parts = df["aired"].str.split(" to ", n=1, expand=True)
    parse = lambda x: pd.to_datetime(x, errors="coerce", format="mixed") if isinstance(x, str) and x.strip() != "?" else pd.NaT
    df["aired_start"] = parts[0].map(parse)
    df["aired_end"] = parts[1].map(parse)
    return df


# ---------------------------------------------------------------- dimensions
def build_dim_anime(df):
    cols = ["anime_id", "name", "english_name", "other_name", "score", "genres", "synopsis", "type", "episodes",
            "aired", "premiered", "status", "producer", "licensors", "studios", "source", "duration", "rating",
            "rank", "popularity", "favourites", "scored_by", "members"]
    return df[cols].copy()


def explode_list(df, col, out):
    x = df[["anime_id", "name", col]].copy()
    x[col] = x[col].str.split(r",\s*")
    x = x.explode(col).rename(columns={col: out})
    x[out] = x[out].str.strip()
    return x[x[out].notna() & (x[out] != "") & (x[out].str.upper() != "UNKNOWN")]


def build_dim_studio_publisher(df):
    s = explode_list(df, "studios", "studio_name").rename(columns={"name": "title"})
    s = s.reset_index(drop=True)
    s.insert(0, "org_id", s.index + 1)
    s["publisher_name"] = None      # not in CSV (manga publisher)
    s["magazine_name"] = None
    return s[["org_id", "title", "studio_name", "publisher_name", "magazine_name", "anime_id"]]


def build_dim_genre(df):
    g = explode_list(df, "genres", "genre_name").rename(columns={"name": "title"}).reset_index(drop=True)
    g.insert(0, "genre_id", g.index + 1)
    g["demographic"] = np.where(g["genre_name"].isin(DEMOGRAPHICS), g["genre_name"], None)
    return g[["genre_id", "title", "genre_name", "demographic", "anime_id"]]


def build_dim_media_format(df):
    t = sorted(df["type"].dropna().unique())
    return pd.DataFrame({"media_key": range(1, len(t) + 1), "media_type": t, "genre_name": None})


def build_dim_date_period(df):
    d = df["aired_start"].dropna().dt.to_period("M").drop_duplicates().sort_values()
    season = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
              6: "Summer", 7: "Summer", 8: "Summer", 9: "Fall", 10: "Fall", 11: "Fall"}
    out = pd.DataFrame({"year": d.dt.year, "month_num": d.dt.month})
    out["period_key"] = out.year * 100 + out.month_num
    out["period_type"] = "MONTH"
    out["quarter"] = "Q" + ((out.month_num - 1) // 3 + 1).astype(str)
    out["anime_season"] = out.month_num.map(season) + " " + out.year.astype(str)
    return out[["period_key", "period_type", "year", "month_num", "quarter", "anime_season"]].reset_index(drop=True)


def build_dim_author():
    return pd.DataFrame({"author_id": pd.Series(dtype="int64"), "title": pd.Series(dtype="object"),
                         "author_name": pd.Series(dtype="object"), "role": pd.Series(dtype="object")})


# ---------------------------------------------------------------- fact
def build_fact(df, media):
    f = df.merge(media[["media_key", "media_type"]], left_on="type", right_on="media_type", how="left")
    f = f.reset_index(drop=True)
    return pd.DataFrame({
        "id": f.index + 1, "media_key": f["media_key"], "title": f["name"], "jp_title": f["other_name"],
        "period_type": "MONTH",
        "raw_period": (f.aired_start.dt.year * 100 + f.aired_start.dt.month).astype("Int64"),
        "volume": pd.array([pd.NA] * len(f), dtype="Int64"), "sales": pd.array([pd.NA] * len(f), dtype="Int64"),
        "anime_id": f["anime_id"], "score": f["score"], "members": f["members"],
        "favourites": f["favourites"], "scored_by": f["scored_by"].astype("Int64"),
        "aired_start": f["aired_start"], "aired_end": f["aired_end"],
    })


# ---------------------------------------------------------------- SCD Type 2
def build_status_scd2(df):
    """Reconstruct each title's status timeline from its air dates.
    Finished titles with a real run: 'Currently Airing' [start, end) -> 'Finished Airing' [end, 9999)."""
    rows = []
    for r in df[["anime_id", "status", "aired_start", "aired_end"]].itertuples(index=False):
        s, e = r.aired_start, r.aired_end
        if r.status == "Finished Airing" and pd.notna(s) and pd.notna(e) and e > s:
            rows.append((r.anime_id, "Currently Airing", s, e, False))
            rows.append((r.anime_id, "Finished Airing", e, FOREVER, True))
        elif r.status == "Not yet aired":
            rows.append((r.anime_id, r.status, s if pd.notna(s) else SNAPSHOT, FOREVER, True))
        else:
            rows.append((r.anime_id, r.status, s, FOREVER, True))
    out = pd.DataFrame(rows, columns=["anime_id", "status", "valid_from", "valid_to", "is_current"])
    out.insert(0, "status_sk", range(1, len(out) + 1))
    return out


TIERS = [(200, 1, "Tier 1 - Major"), (75, 2, "Tier 2 - Established"), (25, 3, "Tier 3 - Mid"), (0, 4, "Tier 4 - Small")]


def tier_of(n):
    return next((rank, label) for th, rank, label in TIERS if n >= th)


def build_studio_tier_scd2(studio, fact):
    """Tier = cumulative catalogue size at each year-end; consecutive years in the same tier collapse to one row."""
    d = studio.merge(fact[["anime_id", "aired_start"]], on="anime_id")
    d["yr"] = d.aired_start.dt.year
    d = d[d.yr <= END_YEAR]          # skip announced-but-future titles
    per = d.dropna(subset=["yr"]).groupby(["studio_name", "yr"]).size().rename("n").reset_index()
    rows = []
    for name, g in per.groupby("studio_name"):
        counts = g.set_index("yr")["n"]
        years = list(range(int(counts.index.min()), END_YEAR + 1))
        cum = counts.reindex(years, fill_value=0).cumsum()
        start, prev = years[0], tier_of(cum.iloc[0])
        for y, n in cum.items():
            t = tier_of(n)
            if t != prev:
                rows.append((name, prev[0], prev[1], start, y - 1, False))
                start, prev = y, t
        rows.append((name, prev[0], prev[1], start, 9999, True))
    out = pd.DataFrame(rows, columns=["studio_name", "tier_rank", "tier", "valid_from_year", "valid_to_year", "is_current"])
    out.insert(0, "tier_sk", range(1, len(out) + 1))
    return out[["tier_sk", "studio_name", "tier", "tier_rank", "valid_from_year", "valid_to_year", "is_current"]]


# ---------------------------------------------------------------- analysis (pandas twin of sql/02_analysis.sql)
def engagement_view(fact, dim_anime, media):
    e = fact.merge(media[["media_key", "media_type"]], on="media_key")
    e["score"] = e["score"].astype(float)
    yrs = ((SNAPSHOT - e.aired_start).dt.days / 365.25).clip(lower=0.25)
    e["members_per_year"] = e["members"] / yrs
    e["favs_per_1k"] = e["favourites"] / e["members"] * 1000
    e["rating_participation"] = e["scored_by"].astype(float) / e["members"]
    e["reliable_score"] = e["score"].where(e["scored_by"] >= MIN_VOTES)
    return e


def run_local_analysis(fact, dim_anime, media, studio, status_scd2, tier_scd2):
    e = engagement_view(fact, dim_anime, media)
    cur = status_scd2[status_scd2.is_current][["anime_id", "status", "valid_from"]]
    e = e.merge(cur, on="anime_id")
    agg = dict(titles=("anime_id", "count"), avg_score=("reliable_score", "mean"))
    pd.options.display.float_format = "{:,.2f}".format
    pd.options.display.width = 200
    pd.options.display.max_columns = 20

    print("\nQ1. Engagement by lifecycle status")
    print(e.groupby("status").agg(**agg, median_velocity=("members_per_year", "median"),
          median_favs_per_1k=("favs_per_1k", "median"), median_rating_participation=("rating_participation", "median")))

    print("\nQ2. Same cohort (TV, started 2023+)")
    c = e[(e.media_type == "TV") & (e.aired_start.dt.year >= 2023) & e.status.isin(["Currently Airing", "Finished Airing"])]
    print(c.groupby("status").agg(**agg, median_members=("members", "median"), median_favs_per_1k=("favs_per_1k", "median")))

    print("\nQ3. Years since 'Finished Airing' row became effective (TV)")
    f = e[(e.status == "Finished Airing") & e.valid_from.notna() & (e.media_type == "TV")].copy()
    f["yrs"] = (SNAPSHOT - f.valid_from).dt.days / 365.25
    f = f[f.yrs > 0]
    f["bucket"] = pd.cut(f.yrs, [0, 1, 3, 5, 10, 20, 200], labels=["0-1y", "1-3y", "3-5y", "5-10y", "10-20y", "20y+"])
    print(f.groupby("bucket", observed=True).agg(**agg, median_members=("members", "median"), median_favs_per_1k=("favs_per_1k", "median")))

    print("\nQ4. Studio tier at time of release")
    j = e.merge(studio[["anime_id", "studio_name"]], on="anime_id").merge(tier_scd2, on="studio_name")
    j = j[(j.aired_start.dt.year >= j.valid_from_year) & (j.aired_start.dt.year <= j.valid_to_year)]
    print(j.groupby("tier").agg(**agg, median_members=("members", "median")))

    print("\nQ5. Studios promoted to a higher tier: 5y before vs 5y after")
    t = tier_scd2.sort_values(["studio_name", "valid_from_year"]).copy()
    t["prev_rank"] = t.groupby("studio_name")["tier_rank"].shift()
    up = t[t.prev_rank.notna() & (t.tier_rank < t.prev_rank)][["studio_name", "valid_from_year"]].rename(columns={"valid_from_year": "promo_year"})
    p = e.merge(studio[["anime_id", "studio_name"]], on="anime_id").merge(up, on="studio_name")
    y = p.aired_start.dt.year
    p = p[(y >= p.promo_year - 5) & (y <= p.promo_year + 4)]
    p["period"] = np.where(p.aired_start.dt.year < p.promo_year, "before promotion", "after promotion")
    print(p.groupby("period").agg(**agg, median_members=("members", "median")))
    print(f"(promotion events: {len(up)})")


# ---------------------------------------------------------------- BigQuery load
def load_to_bigquery(project, tables, dataset="anime_dw"):
    from google.cloud import bigquery
    client = bigquery.Client(project=project)
    client.create_dataset(bigquery.Dataset(f"{project}.{dataset}"), exists_ok=True)
    cfg = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    for name, frame in tables.items():
        frame = frame.copy()
        for c in frame.select_dtypes(include=["datetime64[ns]", "datetime64[us]", "datetime64[s]"]).columns:
            frame[c] = frame[c].dt.date                       # BigQuery DATE (9999-12-31 is valid)
        client.load_table_from_dataframe(frame, f"{project}.{dataset}.{name}", job_config=cfg).result()
        print(f"loaded {name}: {len(frame):,} rows")


def run_pipeline(bq_project=None, analyze=True):
    """Build the star schema + SCD2 tables from the CSV. Optionally load them to BigQuery and print the analysis.
    Returns every table (plus the cleaned raw frame) in a dict so callers can reuse them."""
    raw = load_raw()
    dim_anime = build_dim_anime(raw)
    media = build_dim_media_format(raw)
    studio = build_dim_studio_publisher(raw)
    genre = build_dim_genre(raw)
    period = build_dim_date_period(raw)
    fact = build_fact(raw, media)
    status_scd2 = build_status_scd2(raw)
    tier_scd2 = build_studio_tier_scd2(studio, fact)

    print(f"dim_anime {len(dim_anime):,} | studios {len(studio):,} | genres {len(genre):,} | "
          f"fact {len(fact):,} | status SCD2 {len(status_scd2):,} | tier SCD2 {len(tier_scd2):,}")

    tables = {
        "dim_anime": dim_anime, "dim_studio_publisher": studio, "dim_author": build_dim_author(),
        "dim_media_format": media, "dim_genre": genre, "dim_date_period": period,
        "fact_sales_series": fact, "dim_anime_status_scd2": status_scd2, "dim_studio_tier_scd2": tier_scd2}
    if bq_project:
        load_to_bigquery(bq_project, tables)
    if analyze:
        run_local_analysis(fact, dim_anime, media, studio, status_scd2, tier_scd2)
    return {"raw": raw, **tables}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bq", metavar="PROJECT", help="also load tables to BigQuery")
    args = ap.parse_args()
    run_pipeline(bq_project=args.bq)


if __name__ == "__main__":
    main()
