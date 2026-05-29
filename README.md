# arXiv Explorer

Interactive dashboards for exploring 1M arXiv papers. Two Streamlit apps with category networks, author collaboration graphs, drill-down analytics, and trending statistics.

## Apps

| App | Run | What it does |
|-----|-----|-------------|
| **arXiv Explorer** | `uv run streamlit run arxiv_explorer/app.py` | Dashboard, search, category explorer, author browser, trends & statistics |
| **arXiv Network Explorer** | `uv run streamlit run arxiv_explorer/network_app.py` | Category co-occurrence network, author ego-network, network statistics, drill-down explorer |

## Quick start

```bash
uv sync                          # install dependencies
uv run streamlit run arxiv_explorer/app.py
uv run streamlit run arxiv_explorer/network_app.py
```

## Tests

```bash
uv run pytest tests/ -v
```

## Data

Expects `arxiv_random_sample.parquet` (1M papers) in the repo root. Schema includes `id`, `title`, `abstract`, `authors`, `authors_parsed`, `categories`, `update_date`, `license`, `comments`, `versions`, and more.

A **[data dictionary](data_dictionary.yaml)** documents all 14 source columns and 25 derived columns with types, descriptions, and example values. Both apps surface these descriptions as live help tooltips on metrics, dataframes, and section headers — hover over any labeled element for explanation.

## Features

- **Category aliasing** — 7 legacy→modern mappings (e.g. `math-ph` → `math.MP`)
- **Category network** — force-directed graph of co-occurring research areas
- **Author ego-network** — search any author, view co-author graph with weighted edges
- **Drill-down** — Domain → Category → Author → Papers with breadcrumb navigation
- **Co-occurrence matrix** — overlap fraction between top research areas
- **Networks stats** — per-paper author counts, most prolific authors, multi-area papers
- **Live column help** — hover over any metric, dataframe header, or section heading for a description of what it represents (sourced from [data_dictionary.yaml](data_dictionary.yaml))
