import csv
import time
import re
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
import requests as rq
import lxml as lx
from bs4 import BeautifulSoup

from logger import PipelineLogger

logger = PipelineLogger.get_logger()


def get_media_type(url: str) -> str:
    segment = urlparse(url).path.strip("/").split("/")[0]
    return {"manga": "Manga", "ln": "Light Novel", "anime": "Anime"}.get(segment, "Unknown")


def extract_series_sales(session, slug: str) -> list[dict]:
    url = f"https://mangacodex.com/manga/{slug}"
    url_ln = f"https://mangacodex.com/ln/{slug}"
    raw_rows = []

    # Check both /manga/{slug} and /ln/{slug}
    for target_url in (url, url_ln):
        res_entry = session.get(target_url, params={"sales_tab": "monthly", "page": 1}, timeout=30)
        if res_entry.status_code != 200:
            continue

        soup = BeautifulSoup(res_entry.content, "lxml")
        h1_el = soup.find("h1", class_="manga-header__title")
        if not h1_el:
            continue

        title = h1_el.get_text(strip=True)
        try:
            jp_title = soup.find("p", class_="manga-header__title-jp").get_text(strip=True)
        except AttributeError:
            jp_title = None
            logger.debug("No JP title found for %s (%s)", title, target_url)

        media_type = get_media_type(target_url)

        # 1. Monthly loop
        page_num = 1
        while True:
            res_m = (
                res_entry
                if page_num == 1
                else session.get(target_url, params={"sales_tab": "monthly", "page": page_num}, timeout=30)
            )
            soup_m = BeautifulSoup(res_m.content, "lxml")
            for tr in soup_m.select("table.data-table tbody tr"):
                cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cols) >= 3:
                    raw_rows.append({
                        "media_type": media_type,
                        "title": title,
                        "jp_title": jp_title,
                        "period_type": "Monthly",
                        "raw_period": cols[0],
                        "raw_volume": cols[1],
                        "raw_sales": cols[2],
                    })
            if not soup_m.find("a", string="›"):
                break
            page_num += 1
            time.sleep(0.5)

        # 2. Yearly loop
        page_num = 1
        while True:
            res_y = session.get(target_url, params={"sales_tab": "yearly", "page": page_num}, timeout=30)
            soup_y = BeautifulSoup(res_y.content, "lxml")
            for tr in soup_y.select("table.data-table tbody tr"):
                cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cols) >= 3:
                    raw_rows.append({
                        "media_type": media_type,
                        "title": title,
                        "jp_title": jp_title,
                        "period_type": "Yearly",
                        "raw_period": cols[0],
                        "raw_volume": cols[1],
                        "raw_sales": cols[2],
                    })
            if not soup_y.find("a", string="›"):
                break
            page_num += 1
            time.sleep(0.5)

    return raw_rows


def transform_sales(raw_rows: list[dict], start_idx: int = 1) -> list[list]:

    clean_rows = []
    for idx, row in enumerate(raw_rows, start=start_idx):
        sales_int = int(row["raw_sales"].replace(",", ""))

        vol_clean = (
            row["raw_volume"]
            .replace("Vol ", "")
            .replace("vol.", "")
            .strip()
        )

        clean_rows.append([
            idx,
            row["media_type"],
            row["title"],
            row["jp_title"],
            row["period_type"],
            row["raw_period"],
            vol_clean,
            sales_int,
        ])
    return clean_rows


def write_series_csv(
    session,
    title: str,
    start_idx: int = 1,
    path: str | Path = "data/series_sales_v2.csv",
) -> int:

    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", str(title).lower())
    slug = re.sub(r"[\s-]+", "-", slug).strip("-")
    if not slug:
        logger.warning("Skipping title with empty URL slug: %s", title)
        return 0

    raw_rows = extract_series_sales(session, slug)
    series_row = transform_sales(raw_rows, start_idx=start_idx)
    if not series_row:
        logger.debug("No sales rows found for %s (slug=%s)", title, slug)
        return 0

    file_path = Path(path)
    write_header = not file_path.exists() or file_path.stat().st_size == 0
    header = ["index", "media_type", "title", "jp_title", "period_type", "raw_period", "volume", "sales"]

    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerows(series_row)

    logger.info("Saved %d sales rows for %s -> %s", len(series_row), title, file_path)
    return len(series_row)


if __name__ == "__main__":
    manga_csv = Path("../data/manga_dataset.csv")
    if not manga_csv.exists():
        manga_csv = Path(__file__).resolve().parent.parent / "data" / "manga_dataset.csv"
    df = pd.read_csv(manga_csv)
    logger.info("Starting MangaCodex sales extraction for %d unique titles", df["title"].nunique())
    with rq.Session() as session:
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0"
        })
        next_id = 1
        for title in df["title"].dropna().unique():
            logger.info("Processing %s", title)
            added = write_series_csv(session, title, start_idx=next_id)
            if added > 0:
                logger.info("Saved %d rows for %s (next_id=%d)", added, title, next_id + added)
            next_id += added
            time.sleep(0.5)
