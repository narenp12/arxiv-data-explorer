import os
import polars as pl
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_DATA = os.path.join(HERE, "..", "arxiv_random_sample.parquet")
REMOTE_REPO = "open-index/open-arxiv"


def load_data():
    """Return a LazyFrame from the selected data source.
    Not cached (just a file-open), but _load_remote is cached."""
    source = st.session_state.get("data_source", "auto")
    if source == "local" or (source == "auto" and os.path.exists(LOCAL_DATA)):
        return pl.scan_parquet(LOCAL_DATA)
    return _load_remote()


@st.cache_resource(show_spinner="Downloading arXiv dataset from HuggingFace…")
def _load_remote():
    try:
        from huggingface_hub import snapshot_download
        import glob

        path = snapshot_download(REMOTE_REPO, repo_type="dataset")
        files = sorted(glob.glob(os.path.join(path, "*.parquet")))
        if not files:
            raise FileNotFoundError("No parquet files found in the downloaded dataset")
        return pl.scan_parquet(files)
    except Exception as e:
        if os.path.exists(LOCAL_DATA):
            st.warning(
                f"Could not load remote dataset from HuggingFace ({e}). "
                "Falling back to local sample."
            )
            return pl.scan_parquet(LOCAL_DATA)
        raise
