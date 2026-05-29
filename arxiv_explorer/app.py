import streamlit as st
import polars as pl
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import time
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "arxiv_random_sample.parquet")
sys.path.insert(0, HERE)
import labels

st.set_page_config(page_title="arXiv Explorer", page_icon=None, layout="wide")


# ---------------------------------------------------------------------------
# Cached data loading
# ---------------------------------------------------------------------------
@st.cache_resource
def load_data():
    return pl.scan_parquet(DATA)


@st.cache_data(show_spinner="Preparing date columns…")
def load_date_df(_lf):
    return _lf.with_columns(
        pl.col("update_date").str.to_date("%Y-%m-%d").alias("date"),
        pl.col("update_date").str.to_date("%Y-%m-%d").dt.year().alias("year"),
        pl.col("update_date").str.to_date("%Y-%m-%d").dt.month().alias("month"),
    ).collect()


@st.cache_data(show_spinner="Counting papers per category…")
def get_top_categories(_lf, n=30):
    return (
        _lf.select(pl.col("categories").str.split(" "))
        .explode("categories")
        .group_by("categories")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
        .head(n)
        .with_columns(pl.col("categories").replace(labels.CATEGORY_LABELS).alias("label"))
        .collect()
    )


@st.cache_data
def get_year_counts(_df):
    return _df.group_by("year").agg(pl.len().alias("count")).sort("year").collect()


@st.cache_data
def get_month_counts(_df):
    return _df.group_by("month").agg(pl.len().alias("count")).sort("month").collect()


@st.cache_data
def get_null_counts(_lf):
    return (
        _lf.null_count()
        .melt(value_name="null_count")
        .with_columns((1 - pl.col("null_count") / _lf.select(pl.len()).collect().item()).alias("filled_pct"))
        .sort("filled_pct")
        .collect()
    )


@st.cache_data
def _top50_authors(_lf):
    return (
        _lf.select(pl.col("authors_parsed").list.eval(pl.element().list.first()))
        .explode("authors_parsed")
        .group_by("authors_parsed")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
        .head(50)
        .collect()
    )


@st.cache_data(show_spinner="Counting licenses…")
def get_license_counts(_lf):
    return (
        _lf.group_by("license")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
        .with_columns(
            pl.when(pl.col("license").is_null()).then(pl.lit("Missing"))
            .when(pl.col("license").str.contains("nonexclusive", literal=True)).then(pl.lit("arXiv nonexclusive"))
            .when(pl.col("license").str.contains("by/4.0", literal=True)).then(pl.lit("CC BY 4.0"))
            .when(pl.col("license").str.contains("by-nc-nd/4.0", literal=True)).then(pl.lit("CC BY-NC-ND 4.0"))
            .when(pl.col("license").str.contains("by-nc-sa/4.0", literal=True)).then(pl.lit("CC BY-NC-SA 4.0"))
            .when(pl.col("license").str.contains("by-sa/4.0", literal=True)).then(pl.lit("CC BY-SA 4.0"))
            .when(pl.col("license").str.contains("publicdomain/zero", literal=True)).then(pl.lit("CC0 1.0"))
            .otherwise(pl.lit("Other"))
            .alias("license_short")
        )
        .collect()
    )


@st.cache_data
def search_papers(_lf, query, category, year_range, author):
    result = _lf
    if query:
        parts = query.strip().split()
        cond = None
        for p in parts:
            c = pl.col("title").str.contains(p, literal=True) | pl.col("abstract").str.contains(p, literal=True)
            cond = c if cond is None else (cond & c)
        if cond is not None:
            result = result.filter(cond)
    if category and category != "All":
        result = result.filter(pl.col("categories").str.contains(category, literal=True))
    if year_range:
        result = result.filter(
            pl.col("update_date").str.to_date("%Y-%m-%d").dt.year().is_between(year_range[0], year_range[1])
        )
    if author:
        result = result.filter(pl.col("authors").str.contains(author, literal=True))
    return result.collect()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def page_dashboard():
    st.title("Dashboard")
    lf = load_data()
    date_df = load_date_df(lf)

    total = lf.select(pl.len()).collect().item()
    n_cats = lf.select(pl.col("categories").str.split(" ").explode("categories").unique().len()).collect().item()
    n_authors = lf.select(pl.col("authors_parsed").list.eval(pl.element().list.first())).explode("authors_parsed").unique().len().collect().item()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Papers", f"{total:,}",
                 help="Total number of papers in this 1M arXiv sample dataset")
    col2.metric("Date Range", f"{date_df['date'].min().strftime('%Y-%m-%d')}  →  {date_df['date'].max().strftime('%Y-%m-%d')}",
                 help="Earliest and most recent update dates across all papers in the dataset")
    col3.metric("Categories", f"{n_cats:,}",
                 help="Number of unique arXiv research area categories in the dataset")
    col4.metric("Authors (unique last names)", f"{n_authors:,}",
                 help="Number of unique author surnames in the dataset")

    c1, c2 = st.columns(2)

    with c1:
        year_counts = get_year_counts(date_df)
        fig = px.bar(year_counts, x="year", y="count", title="Papers per Year",
                     labels={"year": "", "count": "Papers"}, height=400)
        fig.update_traces(marker_color="#636efa")
        st.plotly_chart(fig, width='stretch')

    with c2:
        month_counts = get_month_counts(date_df)
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        fig = px.bar(
            month_counts.with_columns(
                pl.col("month").replace_strict(pl.Series(range(1, 13)), pl.Series(month_names)).alias("month_name")
            ),
            x="month_name", y="count", title="Papers per Month",
            labels={"month_name": "", "count": "Papers"}, height=400,
        )
        fig.update_traces(marker_color="#00cc96")
        st.plotly_chart(fig, width='stretch')

    c1, c2 = st.columns(2)

    with c1:
        top_cats = get_top_categories(lf)
        fig = px.bar(top_cats.head(20), x="count", y="label", orientation="h",
                     title="Top 20 Research Areas", labels={"count": "Papers", "label": ""},
                     height=500, text_auto=True)
        fig.update_traces(marker_color="#ab63fa")
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width='stretch')

    with c2:
        lic_counts = get_license_counts(lf)
        fig = px.pie(lic_counts, values="count", names="license_short",
                     title="License Distribution", hole=0.4, height=500)
        fig.update_traces(textinfo="label+percent")
        st.plotly_chart(fig, width='stretch')

    st.subheader("Data Completeness", help="Proportion of non-null values for each column in the dataset")
    null_df = get_null_counts(lf)
    fig = px.bar(null_df, x="column", y="filled_pct", title="",
                 labels={"column": "", "filled_pct": "Non-null proportion"},
                 text_auto=".0%", height=400, color="filled_pct",
                 color_continuous_scale="blues")
    fig.update_traces(textposition="outside")
    fig.update_yaxis(tickformat=".0%", range=[0, 1.15])
    st.plotly_chart(fig, width='stretch')


def page_search():
    st.title("Search Papers")
    lf = load_data()

    with st.sidebar:
        st.header("Filters")
        query = st.text_input("Search title / abstract", placeholder="e.g. quantum gravity")
        cats_series = lf.select(pl.col("categories").str.split(" ")).explode("categories").unique().collect().to_series()
        all_cats = ["All"] + sorted(cats_series.to_list())
        category = st.selectbox("Category", all_cats)
        year_range_series = lf.select(pl.col("update_date").str.slice(0, 4).cast(pl.Int32)).collect()
        year_min = int(year_range_series.min().item())
        year_max = int(year_range_series.max().item())
        year_range = st.slider("Year range", year_min, year_max, (year_min, year_max))
        author = st.text_input("Author", placeholder="e.g. de Leeuw")
        search_btn = st.button("Search", type="primary", width='stretch')

    if "search_results" not in st.session_state:
        st.session_state.search_results = None
    if "search_time" not in st.session_state:
        st.session_state.search_time = 0

    if search_btn or st.session_state.search_results is not None:
        if search_btn:
            with st.spinner("Searching 1M papers…"):
                t0 = time.time()
                st.session_state.search_results = search_papers(
                    lf, query, category, year_range, author
                )
                st.session_state.search_time = time.time() - t0

        results = st.session_state.search_results
        st.info(f"Found **{len(results):,}** papers in {st.session_state.search_time:.2f}s")

        if len(results) > 0:
            per_page = st.selectbox("Results per page", [25, 50, 100], index=0)
            n_pages = max(1, (len(results) + per_page - 1) // per_page)
            page = st.number_input("Page", 1, n_pages, 1)
            start, end = (page - 1) * per_page, page * per_page
            page_df = results.slice(start, end - start)

            for row in page_df.iter_rows(named=True):
                with st.expander(f"{row['id']} — {row['title'][:120]}"):
                    cols = st.columns([3, 1])
                    with cols[0]:
                        st.markdown(f"**Authors:** {row['authors']}")
                        st.markdown(f"**Categories:** {labels.readable_categories(row['categories'])}")
                        st.markdown(f"**Submitted by:** {row['submitter'] or '—'}")
                        st.markdown(f"**Updated:** {row['update_date']}")
                        if row.get("comments"):
                            st.markdown(f"**Comments:** {row['comments']}")
                        if row.get("doi"):
                            st.markdown(f"**DOI:** `{row['doi']}`")
                        if row.get("journal-ref"):
                            st.markdown(f"**Journal ref:** {row['journal-ref']}")
                    with cols[1]:
                        n_vers = len(row["versions"]) if row["versions"] else 0
                        n_auth = len(row["authors_parsed"]) if row["authors_parsed"] else 0
                        st.metric("Versions", n_vers)
                        st.metric("Authors", n_auth)
                    st.markdown("---")
                    st.markdown(f"**Abstract:** {row['abstract'][:500]}…" if len(row.get("abstract", "")) > 500 else f"**Abstract:** {row.get('abstract', '')}")


def page_categories():
    st.title("Category Explorer")
    lf = load_data()

    cat_counts = lf.select(pl.col("categories").str.split(" ").list.len().alias("n_cats")).collect()
    fig = px.histogram(x=cat_counts["n_cats"].clip(upper_bound=10),
                       nbins=10, title="Categories per Paper",
                       labels={"x": "Categories", "count": "Papers"}, height=400)
    fig.update_traces(marker_color="#ab63fa")
    fig.update_xaxes(tickvals=list(range(1, 11)))
    st.plotly_chart(fig, width='stretch')

    top_n = st.slider("Number of top categories", 10, 50, 30)
    top_cats = get_top_categories(lf, top_n)

    fig = px.bar(top_cats, x="count", y="label", orientation="h",
                 title=f"Top {top_n} Research Areas", labels={"count": "Papers", "label": ""},
                 height=min(800, 200 + 18 * top_n), text_auto=True)
    fig.update_traces(marker_color="#00cc96")
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, width='stretch')

    st.subheader("Related Research Areas")
    top10 = [c for c in top_cats["categories"][:10]]
    top10_labels = [labels.readable_category(c) for c in top10]
    with st.spinner("Computing category co-occurrence matrix…"):
        cat_matrix = lf.select(*[pl.col("categories").str.contains(c, literal=True).cast(pl.Int32).alias(c) for c in top10]).collect()
        cooc = cat_matrix.to_numpy().T @ cat_matrix.to_numpy()
        totals = np.diag(cooc).copy()
        cooc_norm = cooc / totals[:, np.newaxis].astype(float)
        np.fill_diagonal(cooc_norm, np.nan)

    short_names = [c.split(".")[-1] if "." in c else c for c in top10]
    fig = px.imshow(cooc_norm, x=short_names, y=short_names,
                    title="How often do these research areas overlap on the same paper?",
                    labels={"x": "Related area", "y": "Research area", "color": "Overlap fraction"},
                    color_continuous_scale="blues", text_auto=".0%", height=600, width=700)
    fig.update_xaxes(ticktext=top10_labels, tickvals=list(range(len(top10))))
    fig.update_yaxes(ticktext=top10_labels, tickvals=list(range(len(top10))))
    st.plotly_chart(fig, width='stretch')

    st.subheader("Browse Papers by Research Area")
    label_to_code = dict(zip(top_cats["label"], top_cats["categories"]))
    selected_label = st.selectbox("Select a research area", top_cats["label"].to_list())
    selected_cat = label_to_code[selected_label]
    if selected_cat:
        papers = lf.filter(pl.col("categories").str.contains(selected_cat, literal=True)).collect()
        st.info(f"{len(papers):,} papers in **{selected_label}**")
        sample = papers.sample(n=min(20, len(papers)), seed=42)
        for row in sample.iter_rows(named=True):
            st.markdown(f"- **{row['id']}** — {row['title'][:150]}")


def page_authors():
    st.title("Authors")
    lf = load_data()

    author_counts = _top50_authors(lf)
    top_author_list = author_counts["authors_parsed"].to_list()

    search_name = st.text_input("Search by author name", placeholder="e.g. Wang")

    if search_name and search_name.strip():
        q = search_name.strip().lower()
        suggestions = [a for a in top_author_list if q in a.lower()][:5]
        if suggestions:
            st.caption("Suggestions:")
            for s in suggestions:
                if st.button(s, key=f"asug_{s}"):
                    st.session_state.author_search_override = s
                    st.rerun()

    effective = st.session_state.pop("author_search_override", None) or search_name

    if effective:
        papers = lf.filter(pl.col("authors").str.contains(effective, literal=True)).collect()
        st.info(f"{len(papers):,} papers match **{effective}**")
        if len(papers) > 0:
            MAX_SHOW = 200
            display = papers.head(MAX_SHOW)
            if len(papers) > MAX_SHOW:
                st.warning(f"Showing first {MAX_SHOW} of {len(papers):,} papers. Refine your search.")
            with st.spinner("Loading paper details…"):
                for row in display.iter_rows(named=True):
                    with st.expander(f"{row['id']} — {row['title'][:120]}"):
                        st.markdown(f"**Authors:** {row['authors']}")
                        st.markdown(f"**Categories:** {labels.readable_categories(row['categories'])}")
                        st.markdown(f"**Abstract:** {row['abstract'][:400]}…")
    else:
        st.subheader("Most Prolific Authors (by last name)")
        fig = px.bar(author_counts.head(30), x="count", y="authors_parsed",
                     orientation="h", title="Top 30 Author Last Names",
                     labels={"count": "Papers", "authors_parsed": ""},
                     height=700, text_auto=True)
        fig.update_traces(marker_color="#ffa15a")
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width='stretch')

    with st.spinner("Computing author distribution…"):
        st.subheader("Authors per Paper Distribution",
                      help=labels.COLUMN_HELP["n_authors"])
        n_authors = lf.select(pl.col("authors_parsed").list.len().alias("n_authors")).collect()
        binned = (
            n_authors
            .with_columns(pl.when(pl.col("n_authors") > 50).then(51).otherwise(pl.col("n_authors")).alias("n_auth_binned"))
            .group_by("n_auth_binned")
            .agg(pl.len().alias("count"))
            .sort("n_auth_binned")
        )
        labels = [str(i) for i in range(1, 51)] + ["51+"]
        fig = make_subplots(rows=1, cols=2, column_widths=[0.7, 0.3],
                            subplot_titles=("Authors per Paper (capped at 50)", "Zoom: 11+"))
        fig.add_trace(go.Bar(x=labels, y=binned["count"], marker_color="#636efa", showlegend=False), row=1, col=1)
        fig.add_trace(go.Bar(x=labels[10:], y=binned["count"][10:], marker_color="#ef553b", showlegend=False), row=1, col=2)
        fig.update_layout(title_text="Author Count Distribution", height=450)
        st.plotly_chart(fig, width='stretch')


def page_trends():
    st.title("Trends & Statistics")
    lf = load_data()
    date_df = load_date_df(lf)

    tab1, tab2, tab3, tab4 = st.tabs(["Temporal", "Versions", "Text", "Comments"])

    with tab1:
        year_counts = get_year_counts(date_df)
        fig = px.bar(year_counts, x="year", y="count", title="Papers per Year",
                     labels={"year": "", "count": "Papers"}, height=450)
        fig.update_traces(marker_color="#636efa")
        st.plotly_chart(fig, width='stretch')

        month_counts = get_month_counts(date_df)
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        fig = px.bar(
            month_counts.with_columns(
                pl.col("month").replace_strict(pl.Series(range(1, 13)), pl.Series(month_names)).alias("month_name")
            ),
            x="month_name", y="count", title="Seasonal Pattern",
            labels={"month_name": "", "count": "Papers"}, height=400,
        )
        fig.update_traces(marker_color="#00cc96")
        st.plotly_chart(fig, width='stretch')

        with st.spinner("Computing activity heatmap…"):
            heatmap_data = date_df.filter(pl.col("year") >= 2010).group_by(["year", "month"]).agg(pl.len().alias("count")).sort(["year", "month"])
            pivot = heatmap_data.pivot(values="count", index="year", on="month", aggregate_function="first")
            month_map = {str(m): month_names[m - 1] for m in range(1, 13)}
            z = pivot.select([pl.col(k).alias(v) for k, v in month_map.items()]).to_numpy()
            fig = px.imshow(z, x=month_names, y=pivot["year"].to_list(),
                            title="Activity Heatmap (Year × Month)",
                            labels={"x": "Month", "y": "Year", "color": "Papers"},
                            color_continuous_scale="blues", aspect="auto", height=600)
            st.plotly_chart(fig, width='stretch')

    with tab2:
        with st.spinner("Computing version statistics…"):
            version_stats = lf.select(pl.col("versions").list.len().alias("n_versions")).collect()
            st.dataframe(version_stats.describe(), width='stretch',
                         column_config={
                             "statistic": st.column_config.TextColumn("Statistic",
                                 help="Statistical measure (count, mean, std, min, max, etc.)"),
                             "n_versions": st.column_config.NumberColumn("Versions",
                                 help=labels.COLUMN_HELP["n_versions"]),
                         },
                         )

            version_binned = (
                version_stats
                .with_columns(pl.when(pl.col("n_versions") > 20).then(21).otherwise(pl.col("n_versions")).alias("n_vers_binned"))
                .group_by("n_vers_binned")
                .agg(pl.len().alias("count"))
                .sort("n_vers_binned")
            )
            labels = [str(i) for i in range(1, 21)] + ["21+"]
            fig = make_subplots(rows=1, cols=2, column_widths=[0.7, 0.3],
                                subplot_titles=("Versions per Paper", "Zoom: 5+"))
            fig.add_trace(go.Bar(x=labels, y=version_binned["count"], marker_color="#636efa", showlegend=False), row=1, col=1)
            fig.add_trace(go.Bar(x=labels[4:], y=version_binned["count"][4:], marker_color="#ef553b", showlegend=False), row=1, col=2)
            fig.update_layout(title_text="Version Distribution", height=450)
            st.plotly_chart(fig, width='stretch')

    with tab3:
        with st.spinner("Analyzing text length…"):
            text_df = lf.select(pl.col("title").str.len_chars().alias("title_len"),
                                pl.col("abstract").str.len_chars().alias("abstract_len")).collect()
            fig = make_subplots(rows=1, cols=2, subplot_titles=("Title Length", "Abstract Length"), shared_yaxes=True)
            fig.add_trace(go.Histogram(x=text_df["title_len"], nbinsx=60, marker_color="#636efa", name="Title"), row=1, col=1)
            fig.add_trace(go.Histogram(x=text_df["abstract_len"].clip(upper_bound=3000), nbinsx=80,
                                       marker_color="#00cc96", name="Abstract"), row=1, col=2)
            fig.update_layout(title_text="Text Length Distributions", height=450, showlegend=False)
            st.plotly_chart(fig, width='stretch')

            sample_text = text_df.sample(n=10_000, seed=42)
            fig = px.scatter(sample_text, x="title_len", y="abstract_len",
                             title="Title vs Abstract Length (10k sample)",
                             labels={"title_len": "Title (chars)", "abstract_len": "Abstract (chars)"},
                             opacity=0.3, height=500)
            st.plotly_chart(fig, width='stretch')

    with tab4:
        with st.spinner("Parsing comments field…"):
            comments_df = lf.select(
                pl.col("comments").str.len_chars().alias("comments_len"),
                pl.col("comments").str.contains(r"\d+\s*pages?", literal=False).alias("has_pages"),
                pl.col("comments").str.contains(r"\d+\s*figures?", literal=False).alias("has_figures"),
                pl.col("comments").str.contains(r"\d+\s*\w*\s*references?", literal=False).alias("has_refs"),
            ).collect()
            st.subheader("Fields detected in comments",
                          help="Counts of papers whose comments field mentions page counts, figure counts, or reference counts")
            c1, c2, c3 = st.columns(3)
            c1.metric("With page count", f"{comments_df['has_pages'].sum():,}",
                       help=labels.COLUMN_HELP["has_pages"])
            c2.metric("With figure count", f"{comments_df['has_figures'].sum():,}",
                       help=labels.COLUMN_HELP["has_figures"])
            c3.metric("With ref count", f"{comments_df['has_refs'].sum():,}",
                       help=labels.COLUMN_HELP["has_refs"])

            fig = px.histogram(x=comments_df["comments_len"].drop_nulls().clip(upper_bound=300),
                               nbins=60, title="Comments Length Distribution",
                               labels={"x": "Characters", "count": "Papers"}, height=400)
            fig.update_traces(marker_color="#ab63fa")
            st.plotly_chart(fig, width='stretch')


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
def main():
    pages = {
        "Dashboard": page_dashboard,
        "Search": page_search,
        "Categories": page_categories,
        "Authors": page_authors,
        "Trends": page_trends,
    }
    with st.sidebar:
        st.title("arXiv Explorer")
        st.markdown("---")
        selected = st.radio("Navigate", list(pages.keys()), index=0)
        st.markdown("---")
        st.caption(f"Dataset: 1M arXiv papers")
        st.caption("Built with Streamlit + Polars + Plotly")

    pages[selected]()


if __name__ == "__main__":
    main()
