"""
Question 2 charts - Audience Hype vs. Actual Retention
Reads the CSVs that q2_audience_retention.py saved to src/output (no BigQuery needed)
and the raw anime-dataset-2026.csv for the title-level scatter.

Run:  python src/plot_q2.py
Saves 3 PNGs to src/output and shows them.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from logger import PipelineLogger

logger = PipelineLogger.get_logger()

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
OUT_DIR = BASE_DIR / "output"
RAW_CSV = PROJECT_ROOT / "data" / "anime-dataset-2026.csv"

RED, BLUE, GREY = "#c0504d", "#4f81bd", "#7f7f7f"


# ---------------------------------------------------------------- data
def load_cohort() -> pd.DataFrame:
    """Rebuild the sql/02 cohort from the raw CSV (finished TV, 8+ episodes, 1,000+ raters)."""
    df = pd.read_csv(RAW_CSV, encoding="utf-8-sig")
    for col in ["Score", "Episodes", "Scored By"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")      # 'UNKNOWN' -> NaN

    unique_name = df["Name"].map(df["Name"].value_counts()) == 1
    cohort = df[
        unique_name
        & (df["Type"] == "TV")
        & (df["Status"] == "Finished Airing")
        & (df["Episodes"] >= 8)
        & df["Score"].notna()
        & (df["Scored By"] >= 1000)
        & (df["Members"] > 0)
    ].copy()
    cohort["abandonment"] = 1 - cohort["Scored By"] / cohort["Members"]
    logger.info("Loaded Q2 cohort from %s (%d rows)", RAW_CSV.name, len(cohort))
    return cohort


# ---------------------------------------------------------------- charts
def chart_hype_vs_satisfaction(cohort: pd.DataFrame, tiers: pd.DataFrame) -> None:
    """Left: every title (audience size vs score) with a trend line.
       Right: average score and abandonment by audience-size quintile."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    x = np.log10(cohort["Members"])
    y = cohort["Score"]
    ax1.scatter(cohort["Members"], y, s=8, alpha=0.25, color=BLUE)

    slope, intercept = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 100)
    ax1.plot(10 ** xs, slope * xs + intercept, color=RED, linewidth=2,
             label=f"trend: +{slope:.2f} score per 10x audience")
    r = np.corrcoef(x, y)[0, 1]
    ax1.set_xscale("log")
    ax1.set_xlabel("Audience volume (members, log scale)")
    ax1.set_ylabel("Viewer score")
    ax1.set_title(f"Bigger audiences score higher (r = {r:.2f}, n = {len(cohort):,})")
    ax1.legend(loc="lower right")

    labels = tiers["audience_tier"].astype(int).astype(str)
    pos = np.arange(len(tiers))
    ax2.bar(pos, tiers["avg_abandonment"].astype(float) * 100, color=RED, alpha=0.85)
    ax2.set_xticks(pos, labels)
    ax2.set_xlabel("Audience-size quintile (1 = smallest, 5 = largest)")
    ax2.set_ylabel("Avg abandonment proxy (%)", color=RED)
    ax2.set_ylim(0, 80)
    for p, v in zip(pos, tiers["avg_abandonment"].astype(float) * 100):
        ax2.text(p, v + 1, f"{v:.0f}%", ha="center", fontsize=9)

    ax3 = ax2.twinx()
    ax3.plot(pos, tiers["avg_score"].astype(float), color="black", marker="o", linewidth=2)
    ax3.set_ylabel("Avg score", color="black")
    ax3.set_ylim(6, 8)
    ax2.set_title("Abandonment falls, scores rise with audience size")

    fig.tight_layout()
    out_file = OUT_DIR / "q2_hype_vs_satisfaction.png"
    fig.savefig(out_file, dpi=150)
    logger.info("Saved chart %s", out_file)


def chart_genre_abandonment(genres: pd.DataFrame, top_n: int = 10) -> None:
    """Size-adjusted abandonment: the worst and best genres once audience size is held equal."""
    ordered = genres.sort_values("size_adj_abandonment", ascending=False)
    picks = pd.concat([ordered.head(top_n), ordered.tail(top_n)]).drop_duplicates("genre_name")
    picks = picks.sort_values("size_adj_abandonment")
    vals = picks["size_adj_abandonment"].astype(float) * 100
    colors = np.where(vals > 0, RED, BLUE)

    fig, ax = plt.subplots(figsize=(9, 8))
    bars = ax.barh(picks["genre_name"], vals, color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.bar_label(bars, labels=[f"{v:+.1f}" for v in vals], padding=3, fontsize=8)
    ax.set_xlabel("Abandonment vs. same-size audiences (percentage points; + = loses more viewers)")
    ax.set_title(f"Genres that lose / keep viewers (size-adjusted, top & bottom {top_n})")
    fig.tight_layout()
    out_file = OUT_DIR / "q2_genre_abandonment.png"
    fig.savefig(out_file, dpi=150)
    logger.info("Saved chart %s", out_file)


def chart_hype_gap(genres: pd.DataFrame) -> None:
    """Hype gap (audience percentile - score percentile) vs size-adjusted abandonment."""
    x = genres["hype_gap"].astype(float)
    y = genres["size_adj_abandonment"].astype(float) * 100
    size = genres["n_titles"].astype(float)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.scatter(x, y, s=size * 1.5, alpha=0.5, color=GREY, edgecolor="black", linewidth=0.5)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.margins(x=0.1, y=0.08)          # keep edge labels (e.g. Harem) inside the frame

    # label the extremes so the chart stays readable
    extremes = pd.concat([
        genres.nlargest(5, "hype_gap"), genres.nsmallest(4, "hype_gap"),
        genres.nlargest(4, "size_adj_abandonment"), genres.nsmallest(3, "size_adj_abandonment"),
    ]).drop_duplicates("genre_name")
    for _, row in extremes.iterrows():
        ax.annotate(row["genre_name"],
                    (float(row["hype_gap"]), float(row["size_adj_abandonment"]) * 100),
                    xytext=(4, 4), textcoords="offset points", fontsize=8)

    ax.set_xlabel("Hype gap  (audience-size percentile minus score percentile)   <- praised | hyped ->")
    ax.set_ylabel("Size-adjusted abandonment (pp)   <- retains | loses viewers ->")
    ax.set_title("Hype vs. retention by genre (bubble size = number of titles)")
    fig.tight_layout()
    out_file = OUT_DIR / "q2_hype_gap.png"
    fig.savefig(out_file, dpi=150)
    logger.info("Saved chart %s", out_file)


# ---------------------------------------------------------------- main
def main(show: bool = True) -> None:
    tiers = pd.read_csv(OUT_DIR / "q2b_audience_tiers.csv")
    genres = pd.read_csv(OUT_DIR / "q2c_genre_abandonment.csv")
    cohort = load_cohort()

    chart_hype_vs_satisfaction(cohort, tiers)
    chart_genre_abandonment(genres)
    chart_hype_gap(genres)
    logger.info("Saved 3 Q2 charts to %s", OUT_DIR)
    if show:
        plt.show()
    else:
        plt.close("all")


if __name__ == "__main__":
    main()
