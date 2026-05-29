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

The apps support two data sources, switchable via the sidebar:

| Source | Size | Papers | Updates | Auto-download |
|--------|------|--------|---------|---------------|
| **Local** (`arxiv_random_sample.parquet`) | 1.6 GB | 1,000,000 | Manual | — |
| **Remote** (`open-index/open-arxiv` on HuggingFace) | 1.4 GB | 2,990,000 | Weekly | First use only; cached after |

When set to **auto** (default), the app uses the local file if present, otherwise downloads the remote dataset.

Both sources share the same 14-column schema (`id`, `title`, `abstract`, `authors`, `authors_parsed`, `categories`, `update_date`, `license`, `comments`, `versions`, and more).

A **[data dictionary](data_dictionary.yaml)** documents all source and derived columns with types, descriptions, and example values. Both apps surface these descriptions as live help tooltips on metrics, dataframes, and section headers.

## Features

- **Category aliasing** — 7 legacy→modern mappings (e.g. `math-ph` → `math.MP`)
- **Category network** — force-directed graph of co-occurring research areas
- **Author ego-network** — search any author, view co-author graph with weighted edges
- **Drill-down** — Domain → Category → Author → Papers with breadcrumb navigation
- **Co-occurrence matrix** — overlap fraction between top research areas
- **Networks stats** — per-paper author counts, most prolific authors, multi-area papers
- **Live column help** — hover over any metric, dataframe header, or section heading for a description of what it represents (sourced from [data_dictionary.yaml](data_dictionary.yaml))
