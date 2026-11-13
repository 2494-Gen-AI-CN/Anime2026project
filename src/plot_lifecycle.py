"""Scatter + trend line: audience size vs. rating, Currently Airing vs Finished Airing."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from etl_and_analysis import load_raw, MIN_VOTES, PROJECT_ROOT
from logger import PipelineLogger

logger = PipelineLogger.get_logger()

COLORS = {"Currently Airing": "#e4572e", "Finished Airing": "#2e6fe4"}
OUTPUT_DIR = PROJECT_ROOT / "outputs"          # change if you want the PNG somewhere else


def make_plot(raw=None, out_path=None, show=False):
    """Draw the chart. Pass the cleaned frame from run_pipeline()['raw'] to avoid re-reading the CSV."""
    df = load_raw() if raw is None else raw
    df = df[df.status.isin(COLORS) & (df.scored_by >= MIN_VOTES) & df.score.notna() & (df.members > 0)].copy()
    df["log_members"] = np.log10(df.members)
    logger.info("Plotting lifecycle scatter (%d titles)", len(df))

    fig, ax = plt.subplots(figsize=(11, 7))
    for status, color in COLORS.items():
        g = df[df.status == status]
        # Finished Airing is ~100x larger, so draw it fainter and underneath
        ax.scatter(g.log_members, g.score, s=14 if status == "Finished Airing" else 28,
                   alpha=0.12 if status == "Finished Airing" else 0.6, color=color, edgecolors="none",
                   zorder=1 if status == "Finished Airing" else 2, label=f"{status} (n={len(g):,})")

        # trend line: median score within 0.25-wide log10(members) bins (min 5 titles per bin)
        bins = np.arange(np.floor(g.log_members.min() * 4) / 4, g.log_members.max() + 0.25, 0.25)
        g = g.assign(bin=pd.cut(g.log_members, bins))
        t = g.groupby("bin", observed=True).agg(x=("log_members", "median"), y=("score", "median"), n=("score", "size"))
        t = t[t.n >= 5]
        ax.plot(t.x, t.y, color=color, lw=3, marker="o", ms=5, zorder=3, label=f"{status} median trend")

    ticks = np.arange(2, 7.5, 1)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{10**t:,.0f}" for t in ticks])
    ax.set_xlabel("Members (log scale)")
    ax.set_ylabel("Score")
    ax.set_title("Audience Size vs. Rating by Lifecycle Status")
    ax.grid(alpha=0.25)
    ax.legend(loc="lower right", frameon=True)
    fig.tight_layout()

    out_path = Path(out_path) if out_path else OUTPUT_DIR / "lifecycle_scatter.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    logger.info("Saved lifecycle scatter chart to %s", out_path)
    if show:
        plt.show()
    return out_path


if __name__ == "__main__":
    make_plot(show=True)
