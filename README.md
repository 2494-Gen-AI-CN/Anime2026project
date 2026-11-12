# Project 0: Anime Adaptation & Sequel Greenlight Analytics Warehouse

## Business Case

**Aether Media Group**, a North American anime licensing and production committee partner, invests millions of dollars annually to co-produce television anime adaptations and acquire Western distribution rights. In the anime industry, an adaptation acts as both a standalone broadcast product and a catalyst for ongoing manga and merchandise demand. However, funding the wrong adaptation or greenlighting a second season for a franchise that loses viewer momentum leaves the committee with heavy financial losses. Rather than relying on social media hype, Aether Media Group's VP of Content Strategy has commissioned our data team to build a centralized BigQuery analytics warehouse from historical anime performance and viewer engagement records (100,000+ rows). Their goal is to establish a data-driven formula for selecting which manga properties to adapt next and identifying which existing single-season shows have earned a profitable Season 2 renewal.

To guide next year's investment slate, this warehouse answers five core business questions:
1. **The Adaptation Advantage:** How do manga and light novel adaptations compare against original scripts and video game adaptations in viewer ratings, audience reach, and distribution formats (`TV`, `Movie`, `ONA`)?
2. **Audience Hype vs. Actual Retention:** How strongly does total audience volume correlate with viewer satisfaction scores, and which genres suffer the highest viewer abandonment before the season finale?
3. **The Greenlight Formula:** What combination of source material, genre, and episode-count bracket (`Single Cour` vs. `Double Cour`) consistently delivers the highest viewer completion rates?
4. **Lifecycle & Status Evolution (SCD Type 2 Analysis):** How do audience engagement velocity and average ratings shift across a title's historical lifecycle as its broadcast status transitions from *Currently Airing* to *Finished Airing* (or as a studio's tier classification changes over time)?
5. **The Sequel Greenlight Engine:** Which completed single-season manga adaptations demonstrate the highest combined audience demand and completion loyalty—making them the top ROI candidates to renew for a second season assuming ongoing source material?

---

## Project Links & Repository Structure

* **Dataset Source:** 
  * [Manga (Download the Manga Dataset)](https://www.kaggle.com/datasets/patelris/anime-and-mang"a-dataset-2026)
  * [Anime](https://www.kaggle.com/datasets/darkbarrierhub/anime-dataset-2026)
  * Scraped Sales Data from [MangaCodex](https://mangacodex.com), series_sale.csv
* **Partner Repository:** 
  * [Paul Ly](https://github.com/2494-Gen-AI-CN/PaulLy)
  * [David Luu](https://github.com/2494-Gen-AI-CN/David_Luu)
```text
projects/P0/
├── README.md                  # Business case, architecture, and runbook
├── credentials/               # Ingestion configuration (raw files, formats, BigQuery targets)
│   ├── your_bq_credentials.json
├── requirements.txt           # Python dependencies
├── src/
│   ├── ingest.py              # Config-driven pandas cleaning & BigQuery staging loader
│   └── transform.py           # Pure pandas validation, cleansing, and feature engineering
├── tests/
│   └── test_transform.py      # Offline pytest suite for cleaning & transformation logic
├── sql/
│   ├── 00_build_star_schema.sql
│   ├── 01_adaptation_advantage.sql
│   ├── 02_hype_vs_retention_correlation.sql
│   ├── 03_greenlight_formula.sql
│   ├── 04_scd2_lifecycle_history.sql
│   └── 05_sequel_greenlight_candidates.sql
├── artifacts/
│   ├── star_schema.png        # Warehouse entity-relationship diagram
│   ├── sample_load_log.csv    # Sample output of the idempotent load log
│   ├── sample_rejects.csv     # Sample output of rejected records with failure reasons
│   └── charts/                # Client-facing Matplotlib visualizations
└── slides/
    └── presentation_deck.pdf  # Client showcase presentation