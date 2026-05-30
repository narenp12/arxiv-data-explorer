# arXiv Network Explorer

Deployed at [arxivexplorer.streamlit.app](https://arxivexplorer.streamlit.app).

Two apps for exploring 1M+ arXiv papers. The **Network Explorer** (`arxiv_explorer/network_app.py`) has network graphs, drill-down explorer, and network statistics. The **Explorer** (`arxiv_explorer/app.py`) is a simpler dashboard with KPIs and paper search.

### Tabs (Network Explorer)

- **Research Area Connections** — select a category to see its top co-occurring neighbors in a force-directed graph
- **Collaboration Network** — search an author to see their weighted co-author ego-graph; click any co-author to explore their network
- **Network Stats** — author count distribution, prolific authors, multi-category papers, searchable author list
- **Drill-Down Explorer** — hierarchical drill-down: Domain → Category → Authors → Papers with breadcrumb navigation

### Data

Two sources switchable via sidebar: local sample (1M papers) or HuggingFace (2.99M papers). Remote source auto-downloads on first use.

### Packages

Streamlit, Polars, NetworkX, Plotly, HuggingFace Hub.

### Category aliases

arXiv renamed some categories over time. The app maps legacy codes to their modern equivalents so they group correctly in graphs and statistics:

`math-ph` → `math.MP`, `physics` → `physics.gen-ph`, `q-alg` → `math.QA`, `q-bio` → `q-bio.OT`, `q-fin` → `q-fin.GN`, `adap-org` → `nlin.AO`, `cmp-lg` → `cs.CL`.