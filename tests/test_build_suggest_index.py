import json
import gzip
import tempfile
from pathlib import Path
import daft
import pytest

from scripts.build_data import build_suggest_index

SAMPLE_DF = daft.from_pydict({
    "id": ["arXiv:quant-ph/0001001", "arXiv:cs.AI/0002002", "arXiv:math.GM/0003003", "arXiv:physics/0004004"],
    "title": ["Quantum Theory", "Artificial Intelligence", "General Mathematics", "Physics Today"],
    "authors": ["Einstein", "Turing", "Gauss", "Feynman"],
    "categories": [["quant-ph"], ["cs.AI"], ["math.GM"], ["physics"]],
})


class TestBuildSuggestIndex:
    def test_output_files_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suggest"
            build_suggest_index(SAMPLE_DF, out)
            assert (out / "meta.json").exists()
            assert (out / "q.json.gz").exists()
            assert (out / "a.json.gz").exists()
            assert (out / "g.json.gz").exists()
            assert (out / "p.json.gz").exists()
            assert (out / "categories.json.gz").exists()

    def test_shard_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suggest"
            build_suggest_index(SAMPLE_DF, out)
            with gzip.open(out / "q.json.gz", "rt") as f:
                data = json.load(f)
            assert "t" in data
            assert "a" in data
            assert ["Quantum Theory", "arXiv:quant-ph/0001001"] in data["t"]

    def test_meta_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suggest"
            build_suggest_index(SAMPLE_DF, out)
            meta = json.loads((out / "meta.json").read_text())
            assert meta["version"] == 1
            assert meta["total_papers"] == 4
            assert isinstance(meta["shards"], dict)

    def test_brotli_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suggest"
            build_suggest_index(SAMPLE_DF, out)
            assert (out / "q.json.br").exists()

    def test_categories_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suggest"
            build_suggest_index(SAMPLE_DF, out)
            with gzip.open(out / "categories.json.gz", "rt") as f:
                data = json.load(f)
            assert "c" in data
            cats = dict(data["c"])
            assert "quant-ph" in cats
            assert "cs.AI" in cats

    def test_non_ascii_normalization(self):
        df = daft.from_pydict({
            "id": ["arXiv:2401.00001"],
            "title": ["Élégant Théorie"],
            "authors": ["René"],
            "categories": [["math.GM"]],
        })
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suggest"
            build_suggest_index(df, out)
            assert (out / "e.json.gz").exists()
            assert not (out / "other.json.gz").exists()

    def test_other_shard_for_non_alpha(self):
        df = daft.from_pydict({
            "id": ["arXiv:2401.00001"],
            "title": ["2024 Trends"],
            "authors": ["Author"],
            "categories": [["cs.IR"]],
        })
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suggest"
            build_suggest_index(df, out)
            assert (out / "other.json.gz").exists()
