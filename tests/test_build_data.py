import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import unittest
import polars as pl

from scripts.build_data import build_category_graph


class TestBuildCategoryGraph(unittest.TestCase):
    def test_basic_graph_structure(self):
        df = pl.DataFrame({
            "categories": ["cs.AI stat.ML", "math.AT", "cs.AI stat.ML"],
            "update_date": ["2023-01-01", "2023-02-01", "2023-03-01"],
        })
        result = build_category_graph(df)
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertIn("metadata", result)

    def test_nodes_have_required_keys(self):
        df = pl.DataFrame({
            "categories": ["cs.AI stat.ML", "math.AT"],
            "update_date": ["2023-01-01", "2023-01-02"],
        })
        result = build_category_graph(df)
        for node in result["nodes"]:
            self.assertIn("id", node)
            self.assertIn("label", node)
            self.assertIn("domain", node)
            self.assertIn("group", node)
            self.assertIn("weight", node)
            self.assertIn("color", node)

    def test_edges_have_required_keys(self):
        df = pl.DataFrame({
            "categories": ["cs.AI stat.ML", "cs.AI math.AT"],
            "update_date": ["2023-01-01", "2023-01-02"],
        })
        result = build_category_graph(df)
        for edge in result["edges"]:
            self.assertIn("source", edge)
            self.assertIn("target", edge)
            self.assertIn("weight", edge)

    def test_metadata_contains_fields(self):
        df = pl.DataFrame({
            "categories": ["cs.AI"],
            "update_date": ["2023-06-15"],
        })
        result = build_category_graph(df)
        meta = result["metadata"]
        self.assertIn("total_nodes", meta)
        self.assertIn("total_edges", meta)
        self.assertIn("last_updated", meta)
        self.assertEqual(meta["last_updated"], "2023-06-15")

    def test_category_aliasing_applied(self):
        df = pl.DataFrame({
            "categories": ["math-ph cs.AI"],
            "update_date": ["2023-01-01"],
        })
        result = build_category_graph(df)
        ids = [n["id"] for n in result["nodes"]]
        self.assertIn("math.MP", ids)
        self.assertNotIn("math-ph", ids)
        self.assertIn("cs.AI", ids)

    def test_duplicate_categories_per_paper_deduplicated(self):
        df = pl.DataFrame({
            "categories": ["cs.AI cs.AI"],
            "update_date": ["2023-01-01"],
        })
        result = build_category_graph(df)
        cs_node = next(n for n in result["nodes"] if n["id"] == "cs.AI")
        self.assertEqual(cs_node["weight"], 1)

    def test_edge_count_correct(self):
        df = pl.DataFrame({
            "categories": ["cs.AI stat.ML math.AT"] * 5,
            "update_date": ["2023-01-01"] * 5,
        })
        result = build_category_graph(df)
        pairs = {(e["source"], e["target"]) for e in result["edges"]}
        self.assertIn(("cs.AI", "stat.ML"), pairs)
        self.assertIn(("cs.AI", "math.AT"), pairs)
        self.assertIn(("math.AT", "stat.ML"), pairs)

    def test_domain_and_color_applied(self):
        df = pl.DataFrame({
            "categories": ["cs.AI stat.ML"],
            "update_date": ["2023-01-01"],
        })
        result = build_category_graph(df)
        cs_node = next(n for n in result["nodes"] if n["id"] == "cs.AI")
        self.assertEqual(cs_node["domain"], "cs")
        self.assertEqual(cs_node["group"], "Computer Science")
        self.assertEqual(cs_node["color"], "#1f77b4")
        stat_node = next(n for n in result["nodes"] if n["id"] == "stat.ML")
        self.assertEqual(stat_node["domain"], "stat")
        self.assertEqual(stat_node["color"], "#2ca02c")

    def test_unknown_domain_falls_back(self):
        df = pl.DataFrame({
            "categories": ["unknown.XXX"],
            "update_date": ["2023-01-01"],
        })
        result = build_category_graph(df)
        node = next(n for n in result["nodes"] if n["id"] == "unknown.XXX")
        self.assertEqual(node["domain"], "unknown")
        self.assertEqual(node["group"], "unknown")
        self.assertEqual(node["color"], "#999999")

    def test_empty_categories(self):
        df = pl.DataFrame({
            "categories": pl.Series([], dtype=pl.Utf8),
            "update_date": pl.Series([], dtype=pl.Utf8),
        })
        result = build_category_graph(df)
        self.assertEqual(result["metadata"]["total_nodes"], 0)
        self.assertEqual(result["metadata"]["total_edges"], 0)

    def test_single_paper_no_edges(self):
        df = pl.DataFrame({
            "categories": ["cs.AI"],
            "update_date": ["2023-01-01"],
        })
        result = build_category_graph(df)
        self.assertEqual(result["metadata"]["total_nodes"], 1)
        self.assertEqual(result["metadata"]["total_edges"], 0)

    def test_total_edges_reasonable(self):
        cats = " ".join([f"cat.A{i}" for i in range(30)])
        rows = [{"categories": cats, "update_date": "2023-01-01"} for _ in range(5)]
        df = pl.DataFrame(rows)
        result = build_category_graph(df)
        self.assertLessEqual(result["metadata"]["total_edges"], 600)
        self.assertGreater(result["metadata"]["total_edges"], 0)

    def test_min_cooc_filter(self):
        df = pl.DataFrame({
            "categories": ["cs.AI stat.ML", "cs.AI stat.ML", "cs.AI stat.ML",
                           "cs.AI stat.ML", "cs.AI stat.ML"],
            "update_date": ["2023-01-01"] * 5,
        })
        result = build_category_graph(df)
        edge_weights = [e["weight"] for e in result["edges"]]
        for w in edge_weights:
            self.assertGreaterEqual(w, 5)

    def test_top_n_categories_capped(self):
        papers = [{"categories": f"cat.A{i}", "update_date": "2023-01-01"}
                  for i in range(300)]
        df = pl.DataFrame(papers)
        result = build_category_graph(df)
        self.assertLessEqual(result["metadata"]["total_nodes"], 200)

    def test_edge_source_target_ordered(self):
        df = pl.DataFrame({
            "categories": ["stat.ML cs.AI"] * 5,
            "update_date": ["2023-01-01"] * 5,
        })
        result = build_category_graph(df)
        for edge in result["edges"]:
            self.assertLess(edge["source"], edge["target"])
