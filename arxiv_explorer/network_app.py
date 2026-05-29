import streamlit as st
import polars as pl
import networkx as nx
import plotly.graph_objects as go
import plotly.express as px
from itertools import combinations
import re

import labels
import data_loader


def _author_full_name_expr():
    return (pl.element().list.get(1).str.strip_chars() + " " + pl.element().list.get(0)).str.strip_chars()


_CATEGORY_ALIASES = {
    "math-ph": "math.MP",
    "chao-dyn": "nlin.CD",
    "solv-int": "nlin.SI",
    "cmp-lg": "cs.CL",
    "patt-sol": "nlin.PS",
    "dg-ga": "math.DG",
    "comp-gas": "nlin.CG",
}

_DOMAIN_NAMES = {
    "cs": "Computer Science",
    "math": "Mathematics",
    "stat": "Statistics",
    "physics": "Physics",
    "cond-mat": "Condensed Matter",
    "astro-ph": "Astrophysics",
    "eess": "Electrical Engineering & Systems Science",
    "q-bio": "Quantitative Biology",
    "q-fin": "Quantitative Finance",
    "econ": "Economics",
    "nlin": "Nonlinear Sciences",
    "nucl": "Nuclear Physics",
    "bayes-an": "Bayesian Analysis",
}

_SUBJECT_COLORS = {
    'cs': '#1f77b4',
    'math': '#ff7f0e',
    'stat': '#2ca02c',
    'physics': '#d62728',
    'astro-ph': '#9467bd',
    'cond-mat': '#8c564b',
    'gr-qc': '#7f7f7f',
    'quant-ph': '#bcbd22',
    'eess': '#17becf',
    'q-bio': '#aec7e8',
    'q-fin': '#ffbb78',
    'econ': '#98df8a',
    'nlin': '#ff9896',
    'nucl': '#c5b0d5',
    'nucl-th': '#c5b0d5',
    'nucl-ex': '#c5b0d5',
    'hep-th': '#e377c2',
    'hep-ph': '#e377c2',
    'hep-lat': '#e377c2',
    'hep-ex': '#e377c2',
    'bayes-an': '#9edae5',
}

_EXTRA_PALETTE = px.colors.qualitative.Set3

def _subject_color(node, data):
    raw = node.split('.')[0]
    if raw in _SUBJECT_COLORS:
        return _SUBJECT_COLORS[raw]
    h = 0
    for c in raw:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return _EXTRA_PALETTE[h % len(_EXTRA_PALETTE)]


def _category_pattern(category):
    """Build a regex pattern matching a category and its aliases at word boundaries."""
    aliases = [k for k, v in _CATEGORY_ALIASES.items() if v == category]
    all_cats = [category] + aliases
    return r'(?:^|\s)(?:' + '|'.join(re.escape(c) for c in all_cats) + r')(?:\s|$)'

st.set_page_config(page_title="arXiv Network Explorer", page_icon=None, layout="wide")
st.title("arXiv Network Explorer")
st.markdown("Explore how research areas and authors are connected in 1M arXiv papers.")


# ---------------------------------------------------------------------------
# Cached data
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Pre-computing category relationships…")
def precompute_category_data(_lf):
    exploded = _lf.select(
        pl.int_range(0, pl.len()).alias("_row_idx"),
        pl.col("categories").str.split(" "),
    ).explode("categories").with_columns(
        pl.col("categories").replace_strict(
            list(_CATEGORY_ALIASES.keys()),
            list(_CATEGORY_ALIASES.values()),
            default=pl.col("categories"),
        ).alias("categories")
    ).unique(subset=["_row_idx", "categories"]).collect()

    paper_counts = (
        exploded.group_by("categories")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )

    cooc = exploded.join(
        exploded, on="_row_idx", suffix="_b"
    ).filter(pl.col("categories") < pl.col("categories_b"))

    cooc_counts = (
        cooc.group_by(["categories", "categories_b"])
        .agg(pl.len().alias("count"))
    )

    return paper_counts, cooc_counts


def build_category_graph(pc_df, cooc_df, top_n, min_cooc):
    """Build a NetworkX graph from pre-computed DataFrames.
    Filtering stays in Polars; only final node/edge creation needs Python."""
    top = pc_df.head(top_n)
    cat_set = set(top["categories"].to_list())

    G = nx.Graph()
    for c, cnt in top.iter_rows():
        G.add_node(c, count=cnt)

    filtered = cooc_df.filter(
        pl.col("categories").is_in(cat_set) &
        pl.col("categories_b").is_in(cat_set) &
        (pl.col("count") >= min_cooc)
    )
    for c1, c2, cnt in filtered.iter_rows():
        G.add_edge(c1, c2, weight=cnt)

    return G


@st.cache_data
def precompute_author_data(_lf, author_name):
    papers = _lf.filter(pl.col("authors").str.contains(author_name, literal=True)).select(
        pl.col("authors_parsed")
    ).collect()

    if len(papers) == 0:
        return None, [], [], 0

    names_df = papers.with_columns(
        pl.col("authors_parsed").list.eval(_author_full_name_expr()).alias("full_names")
    )

    exploded = names_df.with_row_index().explode("full_names")

    q = author_name.lower()
    with_match = exploded.with_columns(
        pl.col("full_names").str.to_lowercase().str.contains(q).alias("is_match")
    )

    center_paper_count = with_match.filter(pl.col("is_match")).select(pl.col("index").n_unique()).item()

    matched_names = set(with_match.filter(pl.col("is_match"))["full_names"].unique().to_list())

    paper_with_match = with_match.filter(pl.col("is_match")).select("index").unique()
    coauthors = with_match.join(paper_with_match, on="index").filter(~pl.col("is_match"))
    coauthor_counts = coauthors.group_by("full_names").agg(pl.len().alias("count")).sort("count", descending=True)
    coauthor_papers = dict(coauthor_counts.iter_rows())

    rows_cache = (
        with_match.filter(~pl.col("is_match"))
        .group_by("index", maintain_order=True)
        .agg(pl.col("full_names"))
        .select("full_names")
    )["full_names"].to_list()

    return matched_names, coauthor_papers, rows_cache, center_paper_count


def build_author_ego_graph(author_name, matched_names, coauthor_papers, rows_cache, center_paper_count, max_coauthors):
    """Build graph from pre-computed data. Co-occurrence pairs are computed
    only for the top N co-authors, avoiding O(k²) explosions from papers
    with hundreds of authors."""
    if center_paper_count == 0:
        return None, []

    sorted_coauthors = sorted(coauthor_papers.items(), key=lambda x: -x[1])
    top_coauthors = sorted_coauthors[:max_coauthors]
    coauthor_set = {name for name, _ in top_coauthors}

    G = nx.Graph()
    G.add_node(author_name, type="center", papers=center_paper_count, size=min(center_paper_count, 200))

    for name, cnt in top_coauthors:
        G.add_node(name, type="coauthor", papers=cnt, size=min(cnt * 3, 100))
        G.add_edge(author_name, name, weight=cnt)

    co_occurrence = {}
    for coauthors in rows_cache:
        present = sorted(coauthor_set.intersection(coauthors))
        for n1, n2 in combinations(present, 2):
            co_occurrence[(n1, n2)] = co_occurrence.get((n1, n2), 0) + 1

    for (n1, n2), cnt in co_occurrence.items():
        G.add_edge(n1, n2, weight=cnt)

    return G, sorted(matched_names)


def plotly_network_graph(G, node_color_map=None, color_values=None, colorscale='Viridis', colorbar_title=None):
    pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)

    center_node = None
    for node, data in G.nodes(data=True):
        if data.get("type") == "center":
            center_node = node
            break

    if center_node and center_node in pos:
        cx, cy = pos[center_node]
        for node in list(pos.keys()):
            pos[node] = (pos[node][0] - cx, pos[node][1] - cy)

    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    node_x, node_y, node_text, node_size = [], [], [], []

    is_cat_graph = not any(d.get("type") in ("center", "coauthor") for _, d in G.nodes(data=True))

    for node, data in G.nodes(data=True):
        node_x.append(pos[node][0])
        node_y.append(pos[node][1])

        readable = labels.readable_category(node)
        paper_count = data.get('count', data.get('papers', '?'))
        if is_cat_graph:
            subj = node.split('.')[0]
            if isinstance(paper_count, int):
                node_text.append(f"<b>{subj}</b> — {readable}<br>Papers: {paper_count:,}")
            else:
                node_text.append(f"<b>{subj}</b> — {readable}")
        elif isinstance(paper_count, int):
            node_text.append(f"{readable}<br>Papers: {paper_count:,}")
        else:
            node_text.append(readable)

        size = data.get("size", data.get("count", 10))
        size = max(5, min(size, 80))
        node_size.append(size)

    marker = dict(size=node_size, line=dict(width=1, color='white'))

    if color_values is not None:
        marker['color'] = color_values
        marker['colorscale'] = colorscale
        marker['showscale'] = True
        marker['colorbar'] = dict(title=colorbar_title or '', thickness=15, len=0.6)
        if node_color_map:
            override = [node_color_map(n, G.nodes[n]) for n in G.nodes()]
            marker['color'] = [o if o is not None else c for o, c in zip(override, color_values)]
    elif node_color_map:
        node_color = [node_color_map(n, G.nodes[n]) for n in G.nodes()]
        marker['color'] = node_color
    else:
        marker['color'] = ['#45b7d1' for _ in G.nodes()]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode='lines',
        line=dict(width=0.5, color='rgba(100,100,100,0.3)'),
        hoverinfo='none'
    )

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode='markers',
        text=node_text, hoverinfo='text',
        marker=marker
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title=None, showlegend=False, hovermode='closest',
        margin=dict(b=5, l=5, r=5, t=5),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        width=None, height=650
    )

    return fig


def _coa_cache_fig(G, center_node):
    coauthor_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "coauthor"]
    weights = [G[n][center_node].get("weight", 1) for n in coauthor_nodes]
    max_w = max(weights) if weights else 1
    fracs = [w / max_w for w in weights] if max_w > 0 else []
    coauthor_colors = px.colors.sample_colorscale('Sunsetdark', fracs) if fracs else []
    color_map = dict(zip(coauthor_nodes, coauthor_colors))
    color_map[center_node] = "#ffd700"

    def coa_c(n, d):
        return color_map.get(n, '#999999')

    st.session_state.co_fig = plotly_network_graph(G, coa_c)


# ---------------------------------------------------------------------------
# Tab 1: Category Co-occurrence Network
# ---------------------------------------------------------------------------
def tab_category_network():
    st.header("Research Area Connections")
    st.markdown("Each circle is a research area. Lines connect areas that frequently appear together on papers. Bigger circles = more papers.")

    lf = data_loader.load_data()

    paper_counts, cooc_counts = precompute_category_data(lf)

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        top_n = st.slider("Number of research areas to show", 15, 100, 40, key="cat_n")
    with c2:
        min_cooc = st.slider("Minimum co-occurrences to draw a connection", 1, 100, 5, key="cat_min")
    with c3:
        build_btn = st.button("Update Network", type="primary", width='stretch')

    if build_btn or "cat_graph" not in st.session_state:
        with st.spinner("Building category network…"):
            G = build_category_graph(paper_counts, cooc_counts, top_n, min_cooc)
            st.session_state.cat_graph = G
            st.session_state.cat_params = (top_n, min_cooc)
            st.session_state.cat_fig = plotly_network_graph(G, _subject_color)
        if build_btn:
            st.toast("Network updated", icon="✅")
    else:
        G = st.session_state.cat_graph

    if G.number_of_nodes() == 0:
        st.warning("No connections meet the threshold. Try lowering the minimum.")
        return

    col1, col2 = st.columns([3, 1])
    with col1:
        st.plotly_chart(st.session_state.cat_fig, width='stretch')

        with col2:
            st.metric("Research areas", G.number_of_nodes(),
                   help="Number of distinct research area categories in the visible network")
            st.metric("Connections", G.number_of_edges(),
                   help="Number of co-occurrence connections between research areas")
            st.metric("Connectivity", f"{nx.density(G):.4f}",
                   help="Network density: fraction of possible connections that exist (0=disconnected, 1=fully connected)")

            with st.container(border=True):
                st.subheader("Most Connected Areas")
                degrees = sorted(G.degree, key=lambda x: -x[1])[:10]
                for node, deg in degrees:
                    count = G.nodes[node].get("count", 0)
                    label = labels.readable_category(node)
                    cols = st.columns([2, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{label}**")
                    with cols[1]:
                        st.markdown(f"{deg} conn.")
                    with cols[2]:
                        st.markdown(f"{count:,} papers")


# ---------------------------------------------------------------------------
# Tab 2: Co-authorship Ego Network
# ---------------------------------------------------------------------------
@st.cache_data
def _top_authors(_lf):
    return (
        _lf.select(pl.col("authors_parsed").list.eval(_author_full_name_expr()).alias("full_name"))
        .explode("full_name")
        .group_by("full_name")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
        .head(20)
        .collect()
    )


def tab_coauthor_network():
    st.header("Collaboration Network")
    st.markdown("Search for an author to see their co-author network. Bigger circles = more co-authored papers.")

    lf = data_loader.load_data()

    top_authors_df = _top_authors(lf)
    top_author_list = top_authors_df["full_name"].to_list()

    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        author_name = st.text_input("Author name", placeholder="e.g. Yi Wang",
                                    value=st.session_state.get("author_name", ""))
    with c2:
        max_co = st.slider("Maximum co-authors to show", 5, 150, 40, key="co_max")
    with c3:
        search_btn = st.button("Find", type="primary", width='stretch')

    if author_name and author_name.strip():
        q = author_name.strip().lower()
        suggestions = [a for a in top_author_list if q in a.lower()][:5]
        if suggestions:
            st.caption("Suggestions:")
            sug_cols = st.columns(min(len(suggestions), 3))
            for i, s in enumerate(suggestions):
                with sug_cols[i % 3]:
                    if st.button(s, key=f"co_sug_{s}"):
                        st.session_state.author_name = s
                        st.session_state.co_auto_search = s
                        st.rerun()
    else:
        st.markdown("**Popular authors:** " + " • ".join(top_author_list[:10]))

    def _build_coa_graph(an, mco):
        md, cp, co, cpc = st.session_state.co_raw
        with st.spinner("Building collaboration graph…"):
            G, mn = build_author_ego_graph(an, md, cp, co, cpc, mco)
            if G is not None:
                _coa_cache_fig(G, an)
                st.session_state.co_graph = G
                st.session_state.matched_names = mn
                st.session_state.co_last_max_co = mco

    def _search_author(name, mco):
        name = name.strip()
        st.session_state.author_name = name
        with st.spinner(f"Searching for '{name}' in 1M papers…"):
            md, cp, co, cpc = precompute_author_data(lf, name)
            if cpc == 0:
                st.error(f"No papers found for '{name}'. Try a different name.")
                st.session_state.pop("co_raw", None)
                st.session_state.pop("co_graph", None)
            else:
                st.session_state.co_raw = (md, cp, co, cpc)
                _build_coa_graph(name, mco)

    auto_name = st.session_state.pop("co_auto_search", None)
    if auto_name:
        _search_author(auto_name, max_co)
    elif search_btn and author_name and author_name.strip():
        _search_author(author_name, max_co)

    if st.session_state.get("co_raw") and st.session_state.get("author_name"):
        prev_co = st.session_state.get("co_last_max_co")
        if st.session_state.get("co_graph") is None or prev_co != max_co:
            an = st.session_state.author_name
            _build_coa_graph(an, max_co)

    if "co_graph" in st.session_state and st.session_state.co_graph is not None:
        G = st.session_state.co_graph
        an = st.session_state.author_name
        center_papers = G.nodes[an]["papers"]

        col1, col2 = st.columns([3, 1])
        with col1:
            st.plotly_chart(st.session_state.co_fig, width='stretch')

        with col2:
            st.metric("Papers by this author", f"{center_papers:,}",
                       help="Total number of papers in the dataset attributed to this author")
            st.metric("Co-authors found", G.number_of_nodes() - 1,
                       help="Number of distinct co-authors connected to this author")
            inter = G.number_of_edges() - (G.number_of_nodes() - 1)
            st.metric("Collaborations between co-authors", inter,
                       help="Number of co-author connections that exist between the author's collaborators (excluding direct links to the author)")

            if "matched_names" in st.session_state:
                with st.container(border=True):
                    st.subheader("Name Matches")
                    for name in st.session_state.matched_names[:8]:
                        st.markdown(f"- {name}")
                    if len(st.session_state.matched_names) > 8:
                        st.caption(f"... and {len(st.session_state.matched_names) - 8} more")

            with st.container(border=True):
                st.subheader("Closest Collaborators")
                edges = sorted(G.edges(data=True), key=lambda e: -e[2].get("weight", 0))
                for u, v, data in edges[:12]:
                    other = v if u == an else u
                    w = data.get("weight", 1)
                    papers = G.nodes[other].get("papers", 0)
                    cols = st.columns([2, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{other}**")
                    with cols[1]:
                        st.markdown(f"{w} paper{'s' if w != 1 else ''}")
                    with cols[2]:
                        st.markdown(f"{papers:,} total")


# ---------------------------------------------------------------------------
# Tab 3: Network Stats
# ---------------------------------------------------------------------------
@st.cache_data
def _author_stats(_lf):
    n_authors = _lf.select(pl.col("authors_parsed").list.len().alias("n_authors")).collect()
    return (
        int((n_authors["n_authors"] == 1).sum()),
        int((n_authors["n_authors"] >= 2).sum()),
        int((n_authors["n_authors"] >= 100).sum()),
        int((n_authors["n_authors"] >= 1000).sum()),
    )


@st.cache_data
def _prolific_authors(_lf):
    return (
        _lf.select(pl.col("authors_parsed").list.eval(_author_full_name_expr()).alias("full_name"))
        .explode("full_name")
        .group_by("full_name")
        .agg(pl.len().alias("papers"))
        .sort("papers", descending=True)
        .head(20)
        .with_columns((pl.col("papers") / pl.col("papers").max() * 100).cast(pl.Int32).alias("relative"))
        .collect()
    )


@st.cache_data
def _overlap_stats(_lf):
    row = _lf.select(
        pl.len().alias("total"),
        pl.col("categories").str.split(" ").list.len().gt(1).sum().alias("multi_cat"),
    ).collect()
    return int(row["total"][0]), int(row["multi_cat"][0])


def tab_network_stats():
    st.header("Network Statistics")
    lf = data_loader.load_data()

    with st.spinner("Computing network statistics…"):

        with st.container(border=True):
            st.subheader("Authors per Paper",
                          help=labels.COLUMN_HELP["n_authors"])
            solo, multi, large, huge = _author_stats(lf)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Single author", f"{solo:,}",
                       help="Papers with exactly one author")
            c2.metric("Multiple authors", f"{multi:,}",
                       help="Papers with two or more authors")
            c3.metric("100+ co-authors", f"{large:,}",
                       help="Papers listing 100 or more authors")
            c4.metric("1000+ co-authors", f"{huge:,}",
                       help="Papers listing 1000 or more authors")

        with st.container(border=True):
            st.subheader("Most Prolific Authors",
                          help="Authors with the highest paper counts in the dataset")
            author_counts = _prolific_authors(lf)

            col_chart, col_table = st.columns([3, 2])
            with col_chart:
                fig = px.bar(author_counts.head(10), x="papers", y="full_name",
                             orientation="h", title="Top 10",
                             labels={"papers": "Papers", "full_name": ""},
                             height=400, text_auto=True)
                fig.update_traces(marker_color="#636efa")
                fig.update_layout(yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, width='stretch')

            with col_table:
                st.dataframe(author_counts, width='stretch', hide_index=True,
                             column_config={
                                 "full_name": st.column_config.TextColumn("Author",
                                     help="Author's full name (first + last) constructed from authors_parsed"),
                                 "papers": st.column_config.NumberColumn("Papers", format="%d",
                                     help=labels.COLUMN_HELP["papers"]),
                                 "relative": st.column_config.NumberColumn("vs #1", format="%d%%",
                                     help="Percentage of papers relative to the most prolific author"),
                             })

        with st.container(border=True):
            st.subheader("Research Area Overlap",
                          help="Papers tagged with more than one arXiv category")
            total, multi_cat_papers = _overlap_stats(lf)
            st.metric("Papers spanning multiple research areas",
                       f"{multi_cat_papers:,} ({multi_cat_papers / total * 100:.1f}% of all papers)",
                       help="Papers tagged with more than one arXiv category, indicating interdisciplinary research")


# ---------------------------------------------------------------------------
# Tab 4: Drill Down
# ---------------------------------------------------------------------------
@st.cache_data
def _domain_counts(_pc):
    return _pc.with_columns(
        pl.col("categories").str.split(".").list.first().alias("domain")
    ).group_by("domain").agg(
        pl.sum("count").alias("papers"),
        pl.len().alias("subcategories"),
    ).sort("papers", descending=True)


@st.cache_data(show_spinner="Finding authors…")
def _category_authors(_lf, category):
    pattern = _category_pattern(category)
    return (
        _lf.filter(pl.col("categories").str.contains(pattern))
        .select(pl.col("authors_parsed").list.eval(pl.element().list.first()))
        .explode("authors_parsed")
        .drop_nulls()
        .group_by("authors_parsed")
        .agg(pl.len().alias("papers"))
        .sort("papers", descending=True)
        .collect()
    )


@st.cache_data(show_spinner="Loading papers…")
def _author_papers(_lf, category, author):
    pattern = _category_pattern(category)
    return _lf.filter(
        pl.col("categories").str.contains(pattern)
        & pl.col("authors_parsed")
        .list.eval(pl.element().list.first())
        .list.contains(author)
    ).select("id", "title", "categories", "update_date").sort("update_date", descending=True).collect()


def tab_drill_down():
    st.header("Drill Down Explorer")
    st.markdown("Click a tile to drill deeper: **Domain → Category → Author → Papers**")

    lf = data_loader.load_data()
    pc, _ = precompute_category_data(lf)

    for k in ["drill_domain", "drill_cat", "drill_author"]:
        if k not in st.session_state:
            st.session_state[k] = None

    col_back, col_path = st.columns([1, 5])
    with col_back:
        if st.session_state.drill_domain and st.button("⬆ Back", width='stretch'):
            if st.session_state.drill_author:
                st.session_state.drill_author = None
            elif st.session_state.drill_cat:
                st.session_state.drill_cat = None
            else:
                st.session_state.drill_domain = None
            st.rerun()
    with col_path:
        parts = []
        if st.session_state.drill_domain:
            d = st.session_state.drill_domain
            parts.append(f"**{d}**")
        if st.session_state.drill_cat:
            c = st.session_state.drill_cat
            parts.append(f"`{c}`")
        if st.session_state.drill_author:
            a = st.session_state.drill_author
            parts.append(a)
        if parts:
            st.markdown("**Path**  \n" + " › ".join(parts))

    st.divider()

    if not st.session_state.drill_domain:
        _render_domains(pc)
    elif not st.session_state.drill_cat:
        _render_categories(pc)
    elif not st.session_state.drill_author:
        _render_authors(lf)
    else:
        _render_papers(lf)


def _render_domains(pc):
    st.subheader("Select a Research Domain")
    data = _domain_counts(pc)
    st.caption(f"{len(data)} domains, {pc.select(pl.sum('count')).item():,} total papers")
    cols = st.columns(4)
    for i, (domain, papers, subs) in enumerate(data.iter_rows()):
        with cols[i % 4]:
            color = _subject_color(domain, {})
            label = domain.replace("-", " ").title()
            full = _DOMAIN_NAMES.get(domain) or labels.readable_category(domain) or domain
            with st.container(border=True):
                st.markdown(
                    f"<div style='border-left:4px solid {color};padding-left:8px'>"
                    f"<strong>{label}</strong></div>",
                    unsafe_allow_html=True,
                )
                st.caption(full)
                st.markdown(f"**{papers:,}** papers · {subs} sub-categories")
                if st.button("Explore →", key=f"dom_{domain}", width='stretch'):
                    st.session_state.drill_domain = domain
                    st.rerun()


def _render_categories(pc):
    st.subheader(f"Categories in **{st.session_state.drill_domain}**")
    prefix = st.session_state.drill_domain + "."
    cats = pc.filter(
        pl.col("categories").str.starts_with(prefix)
        | (pl.col("categories") == st.session_state.drill_domain)
    ).sort("count", descending=True)
    st.caption(f"{len(cats)} sub-categories")
    col_w = st.columns(3)
    for i, (cat, cnt) in enumerate(cats.iter_rows()):
        with col_w[i % 3]:
            color = _subject_color(cat, {})
            label = labels.readable_category(cat)
            with st.container(border=True):
                st.markdown(
                    f"<div style='border-left:4px solid {color};padding-left:8px'>"
                    f"<strong>{label}</strong></div>",
                    unsafe_allow_html=True,
                )
                st.caption(cat)
                st.markdown(f"**{cnt:,}** papers")
                if st.button("Browse →", key=f"cat_{cat}", width='stretch'):
                    st.session_state.drill_cat = cat
                    st.rerun()


def _render_authors(lf):
    cat = st.session_state.drill_cat
    st.subheader(f"Authors in **{labels.readable_category(cat)}**")
    data = _category_authors(lf, cat)
    st.caption(f"{len(data)} unique authors")

    c1, c2 = st.columns([2, 1])
    with c1:
        search = st.text_input("Search for an author (last name)", key="drill_author_search")
    with c2:
        min_papers = st.number_input("Min papers", min_value=1, max_value=1000, value=1, key="drill_min_papers")

    if search:
        search_lc = search.strip().lower()
        matches = data.filter(
            pl.col("authors_parsed").str.to_lowercase().str.contains(search_lc)
            & (pl.col("papers") >= min_papers)
        ).head(20)
        if len(matches) == 0:
            st.warning(f"No authors matching '{search}' with ≥{min_papers} papers")
        else:
            st.caption(f"Found {len(matches):,} author(s) matching '{search}'")
            max_p = matches["papers"].max()
            display = matches.with_columns(
                (pl.col("papers") / max_p * 100).cast(pl.Int32).alias("pct")
            )
            ev = st.dataframe(
                display,
                column_config={
                    "authors_parsed": st.column_config.TextColumn("Author",
                        help="Author's surname (last name)"),
                    "papers": st.column_config.NumberColumn("Papers", format="%d",
                        help=labels.COLUMN_HELP["papers"]),
                    "pct": st.column_config.ProgressColumn("% of Top", format="%d%%",
                        min_value=0, max_value=100,
                        help="Percentage of papers relative to the top author in this category"),
                },
                hide_index=True,
                width='stretch',
                on_select="rerun",
                selection_mode="single-row",
            )
            if ev["selection"]["rows"]:
                idx = ev["selection"]["rows"][0]
                st.session_state.drill_author = display["authors_parsed"][idx]
                st.rerun()
    else:
        st.caption(f"Authors with ≥{min_papers} papers")
        filtered = data.filter(pl.col("papers") >= min_papers)
        max_p = filtered["papers"].max()
        display = filtered.with_columns(
            (pl.col("papers") / max_p * 100).cast(pl.Int32).alias("pct")
        )
        ev = st.dataframe(
            display,
            column_config={
                "authors_parsed": st.column_config.TextColumn("Author",
                    help="Author's surname (last name)"),
                "papers": st.column_config.NumberColumn("Papers", format="%d",
                    help=labels.COLUMN_HELP["papers"]),
                "pct": st.column_config.ProgressColumn("% of Top", format="%d%%",
                    min_value=0, max_value=100,
                    help="Percentage of papers relative to the top author in this category"),
            },
            hide_index=True,
            width='stretch',
            on_select="rerun",
            selection_mode="single-row",
        )
        if ev["selection"]["rows"]:
            idx = ev["selection"]["rows"][0]
            st.session_state.drill_author = display["authors_parsed"][idx]
            st.rerun()


def _render_papers(lf):
    cat = st.session_state.drill_cat
    author = st.session_state.drill_author
    st.subheader(f"Papers by **{author}** in **{labels.readable_category(cat)}**")
    papers = _author_papers(lf, cat, author)
    st.caption(f"{len(papers)} papers")

    for row in papers.iter_rows():
        pid, title, cats, date = row
        with st.container(border=True):
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.markdown(f"[{pid}](https://arxiv.org/abs/{pid})")
                st.markdown(f"**{title}**")
            with col_b:
                st.markdown(f"📅 {date}")
            st.markdown(f"**Categories:** {labels.readable_categories(cats)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if "data_source" not in st.session_state:
        st.session_state.data_source = "auto"

    with st.sidebar:
        st.radio(
            "Data source",
            ["auto", "local", "remote (HuggingFace)"],
            index=["auto", "local", "remote (HuggingFace)"].index(
                st.session_state.data_source
            ),
            key="data_source",
            help="auto: local sample if available, otherwise download from HuggingFace",
        )
        src = st.session_state.data_source
        if src == "remote (HuggingFace)":
            st.caption("Dataset: 2.99M arXiv papers (HuggingFace)")
        else:
            st.caption("Dataset: 1M arXiv papers (local sample)")
        st.caption("Built with Streamlit + Polars + Plotly")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Category Network", "Co-authorship Network", "Stats", "Drill Down",
    ])

    with tab1:
        tab_category_network()
    with tab2:
        tab_coauthor_network()
    with tab3:
        tab_network_stats()
    with tab4:
        tab_drill_down()


if __name__ == "__main__":
    main()
