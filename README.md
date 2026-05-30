# arXiv Network Explorer

Two Streamlit apps for exploring 1M+ arXiv papers. Both use the same data source and share components (`data_loader.py`, `labels.py`).

**arXiv Network Explorer** (`arxiv_explorer/network_app.py`) — network graphs, drill-down explorer, network statistics. This is the primary app.

**arXiv Explorer** (`arxiv_explorer/app.py`) — dashboard KPIs, paper search, trend charts. Subset of the network app's functionality.

---

## Quick start

```bash
uv sync
uv run streamlit run arxiv_explorer/network_app.py
```

## Tests

```bash
uv run pytest tests/ -v
```

---

## Tabs (Network Explorer)

### Research Area Connections

Shows how arXiv categories co-occur. Select a category from the dropdown. The graph displays its top-connected neighbors. Node size = paper count. Click any connected area to jump to its graph. Gold node with dark border = the selected area.

### Collaboration Network

Search for an author by name. Displays a weighted ego-graph of co-authors. Node size and color intensity reflect collaboration frequency. Lists name variants if the author appears under multiple formats. Click any co-author to search their network.

### Network Stats

Per-paper author count distribution. Top 30 most prolific authors. Multi-category paper statistics. Searchable, paginated list of all author names ranked by paper count.

### Drill-Down Explorer

Hierarchical navigation: Domain → Category → Authors → Papers. Breadcrumb path with back button. Supports filtering by multiple co-authors (comma-separated). Adjustable results cap.

---

## Data

Two data sources, switchable via sidebar:

| Source | Papers | Size |
|--------|--------|------|
| Local sample (`arxiv_random_sample.parquet`) | 1,000,000 | 1.6 GB |
| Remote (HuggingFace `open-index/open-arxiv`) | 2,990,000 | 1.4 GB |

Remote source auto-downloads on first use and caches locally. Switching sources invalidates all caches and rebuilds graphs.

### Schema

| Column | Description |
|--------|-------------|
| `id` | arXiv ID |
| `title` | Paper title |
| `abstract` | Paper abstract |
| `authors` | Comma-separated author names (raw string) |
| `authors_parsed` | Parsed names as `[[last, first, middle], ...]` |
| `categories` | Space-separated category codes |
| `update_date` | Last update timestamp |
| `license` | License |
| `comments` | Author comments (pages, figures, references) |
| `versions` | Version history with timestamps |
| `journal-ref`, `report-no`, `doi` | Publication metadata |

Full details in [data_dictionary.yaml](data_dictionary.yaml). Help tooltips throughout the app source from the same file.

### Packages

Streamlit, Polars, NetworkX, Plotly, HuggingFace Hub.

---

## Deployment

[Streamlit Community Cloud](https://share.streamlit.io):

1. New app → select this repo
2. Main file path: `arxiv_explorer/network_app.py`
3. Auto-deploys on push to main branch

---

## Category aliases

Legacy codes mapped to current equivalents:

| Legacy | Modern |
|--------|--------|
| `math-ph` | `math.MP` |
| `physics` | `physics.gen-ph` |
| `q-alg` | `math.QA` |
| `q-bio` | `q-bio.OT` |
| `q-fin` | `q-fin.GN` |
| `adap-org` | `nlin.AO` |
| `cmp-lg` | `cs.CL` |
