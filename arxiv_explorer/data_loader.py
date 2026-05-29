import os
import polars as pl
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_DATA = os.path.join(HERE, "..", "arxiv_random_sample.parquet")
REMOTE_REPO = "open-index/open-arxiv"


def load_data() -> pl.LazyFrame:
    """Return a LazyFrame from the selected data source.
    Not cached (just a file-open), but _load_remote is cached."""
    source = st.session_state.get("data_source", "auto")
    if source == "local" or (source == "auto" and os.path.exists(LOCAL_DATA)):
        return pl.scan_parquet(LOCAL_DATA)
    return _load_remote()


def render_sidebar_data_source():
    """Render the data source radio and caption in the sidebar.
    Shared between app.py and network_app.py."""
    prev = st.session_state.get("data_source")
    if "data_source" not in st.session_state:
        st.session_state.data_source = "auto"
    # Handle case where session state has invalid value (e.g., from old version)
    options = ["auto", "local", "remote (HuggingFace)"]
    if st.session_state.data_source not in options:
        st.session_state.data_source = "auto"
    st.sidebar.markdown("#### Data Source")
    st.sidebar.radio(
        "Source",
        options,
        index=options.index(st.session_state.data_source),
        key="data_source",
        label_visibility="collapsed",
        help="auto: local sample if available, otherwise download from HuggingFace",
    )
    curr = st.session_state.data_source
    if prev is not None and prev != curr:
        st.cache_data.clear()
        st.cache_resource.clear()
    src = curr
    if src == "remote (HuggingFace)":
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
        return pl.scan_parquet(files)
    except (ImportError, OSError, FileNotFoundError) as e:
        if os.path.exists(LOCAL_DATA):
            st.warning(
                f"Could not load remote dataset from HuggingFace ({e}). "
                "Falling back to local sample."
            )
            return pl.scan_parquet(LOCAL_DATA)
        raise
