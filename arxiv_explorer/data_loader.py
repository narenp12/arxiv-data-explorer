import os
import polars as pl
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_DATA = os.path.join(HERE, "..", "arxiv_random_sample.parquet")
REMOTE_REPO = "open-index/open-arxiv"

# Session-state keys that hold computed data derived from the current data source.
# All are cleared when the user switches sources to prevent stale-state crashes.
_DATA_STATE_KEYS = {
    # Category network
    "cat_graph",
    "cat_ego",
    "_cat_ego_forward",
    # Coauthor network
    "co_fig",
    "co_graph",
    "co_raw",
    "co_author_name",
    "matched_names",
    "co_last_max_co",
    "co_auto_search",
    # Drill-down
    "drill_domain",
    "drill_cat",
    "drill_authors",
    "drill_paper",
    # Search
    "search_results",
    "search_time",
    "author_search_override",
}


def _is_lfs_pointer(path) -> bool:
    """Return True if the file at path is an un-downloaded git-LFS pointer."""
    with open(path, "rb") as f:
        head = f.read(40)
    return head.startswith(b"version https://git-lfs")


def load_data() -> pl.LazyFrame:
    """Return a LazyFrame from the selected data source.
    Not cached (just a file-open), but _load_remote is cached."""
    source = st.session_state.get("data_source", "local sample")
    if source == "local sample":
        if os.path.exists(LOCAL_DATA):
            if _is_lfs_pointer(LOCAL_DATA):
                st.info(
                    "Local sample is a git-LFS pointer (not downloaded); loading from HuggingFace…"
                )
            else:
                return pl.scan_parquet(LOCAL_DATA)
        else:
            st.info("Local sample not found, loading from HuggingFace…")
    return _load_remote()


def render_sidebar_data_source():
    """Render the data source radio and caption in the sidebar.
    Shared between app.py and network_app.py."""
    if "data_source" not in st.session_state:
        st.session_state.data_source = "local sample"
    prev = st.session_state.get("_prev_data_source")
    st.sidebar.markdown("#### Data Source")
    options = ["local sample", "remote (HuggingFace)"]
    st.sidebar.radio(
        "Source",
        options,
        index=options.index(st.session_state.data_source),
        key="data_source",
        label_visibility="collapsed",
    )
    curr = st.session_state.data_source
    if prev is not None and prev != curr:
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state._data_reset = True
        for key in _DATA_STATE_KEYS:
            st.session_state.pop(key, None)
    st.session_state._prev_data_source = curr
    if curr == "remote (HuggingFace)":
        st.sidebar.caption(":cloud: 2.99M arXiv papers (HuggingFace)")
    else:
        st.sidebar.caption(":computer: 1M arXiv papers (local sample)")
    st.sidebar.divider()
    st.sidebar.caption("Built with Streamlit · Polars · Plotly")


@st.cache_resource(show_spinner="Downloading arXiv dataset from HuggingFace…")
def _load_remote() -> pl.LazyFrame:
    try:
        from huggingface_hub import snapshot_download
        import glob

        path = snapshot_download(REMOTE_REPO, repo_type="dataset")
        files = sorted(glob.glob(os.path.join(path, "**", "*.parquet"), recursive=True))
        if not files:
            raise FileNotFoundError("No parquet files found in the downloaded dataset")
        lf = pl.scan_parquet(files)
        schema = lf.collect_schema()
        renames = {}
        if "journal_ref" in schema and "journal-ref" not in schema:
            renames["journal_ref"] = "journal-ref"
        if "report_no" in schema and "report-no" not in schema:
            renames["report_no"] = "report-no"
        if renames:
            lf = lf.rename(renames)
        exprs = []
        if isinstance(schema.get("authors_parsed"), pl.String):
            exprs.append(
                pl.col("authors_parsed").str.json_decode(pl.List(pl.List(pl.Utf8)))
            )
        if isinstance(schema.get("versions"), pl.String):
            exprs.append(
                pl.col("versions").str.json_decode(
                    pl.List(
                        pl.Struct(
                            [
                                pl.Field("version", pl.Utf8),
                                pl.Field("created", pl.Utf8),
                            ]
                        )
                    )
                )
            )
        if exprs:
            lf = lf.with_columns(*exprs)
        return lf
    except (ImportError, OSError, FileNotFoundError) as e:
        if os.path.exists(LOCAL_DATA):
            st.warning(
                f"Could not load remote dataset from HuggingFace ({e}). "
                "Falling back to local sample."
            )
            return pl.scan_parquet(LOCAL_DATA)
        raise
