import sys
import os
from unittest.mock import MagicMock

# Mock streamlit BEFORE any module-level code runs
_st_mock = MagicMock()
_st_mock.cache_data = lambda f=None, **kw: f if callable(f) else (lambda g: g)
_st_mock.session_state = {}
_st_mock.spinner = lambda msg=None: MagicMock().__enter__.return_value
sys.modules["streamlit"] = _st_mock

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "arxiv_explorer")
sys.path.insert(0, SRC)

import unittest
import networkx as nx
import polars as pl
import plotly.graph_objects as go
import network_app as m
import labels


class TestSubjectColor(unittest.TestCase):
    def test_known_subjects(self):
        data = {"count": 100}
        fn = m._subject_color
        self.assertEqual(fn("cs.AI", data), "#1f77b4")
        self.assertEqual(fn("math.AG", data), "#ff7f0e")
        self.assertEqual(fn("stat.ML", data), "#2ca02c")
        self.assertEqual(fn("physics.optics", data), "#d62728")
        self.assertEqual(fn("astro-ph.CO", data), "#9467bd")
        self.assertEqual(fn("cond-mat.mtrl-sci", data), "#8c564b")
        self.assertEqual(fn("gr-qc", data), "#7f7f7f")

    def test_hep_group(self):
        data = {"count": 50}
        pink = "#e377c2"
        for cat in ["hep-th", "hep-ph", "hep-lat", "hep-ex"]:
            self.assertEqual(m._subject_color(cat, data), pink)

    def test_consistent_unknown(self):
        data = {"count": 10}
        self.assertEqual(
            m._subject_color("random.XYZ", data),
            m._subject_color("random.XYZ", data),
        )

    def test_different_unknown(self):
        colors = {m._subject_color(f"subj{i}.X", {}) for i in range(10)}
        self.assertGreaterEqual(len(colors), 5)


class TestBuildCategoryGraph(unittest.TestCase):
    def setUp(self):
        self.build = m.build_category_graph
        self.pc = pl.DataFrame({
            "categories": ["cs.AI", "math.AT", "stat.ML", "physics.optics"],
            "count": [100, 80, 60, 40],
        })
        self.cooc = pl.DataFrame({
            "categories": ["cs.AI", "cs.AI", "math.AT"],
            "categories_b": ["math.AT", "stat.ML", "stat.ML"],
            "count": [30, 15, 5],
        })

    def test_basic(self):
        G = self.build(self.pc, self.cooc, top_n=4, min_cooc=10)
        self.assertEqual(G.number_of_nodes(), 4)
        self.assertEqual(G.number_of_edges(), 2)

    def test_min_cooc_filter(self):
        self.assertEqual(
            self.build(self.pc, self.cooc, 4, 20).number_of_edges(), 1
        )

    def test_top_n_limit(self):
        self.assertEqual(
            self.build(self.pc, self.cooc, 2, 1).number_of_nodes(), 2
        )

    def test_isolated_nodes(self):
        G = self.build(self.pc, self.cooc, 4, 100)
        self.assertEqual(G.number_of_nodes(), 4)
        self.assertEqual(G.number_of_edges(), 0)

    def test_node_attributes(self):
        G = self.build(self.pc, self.cooc, 1, 1)
        self.assertEqual(G.nodes["cs.AI"]["count"], 100)

    def test_edge_weights(self):
        G = self.build(self.pc, self.cooc, 4, 10)
        self.assertEqual(G.edges[("cs.AI", "math.AT")]["weight"], 30)


class TestBuildAuthorEgoGraph(unittest.TestCase):
    def setUp(self):
        self.build = m.build_author_ego_graph

    def test_empty_input(self):
        G, mn = self.build("Smith", set(), {}, [], 0, 10)
        self.assertIsNone(G)
        self.assertEqual(mn, [])

    def test_single_coauthor(self):
        rows = [["Alice", "Bob"]]
        G, mn = self.build("Alice", {"Alice"}, {"Bob": 5}, rows, 5, 10)
        self.assertIn("Alice", G)
        self.assertIn("Bob", G)
        self.assertEqual(G["Alice"]["Bob"]["weight"], 5)

    def test_max_coauthors_limit(self):
        papers = {f"Co{i}": i for i in range(20)}
        rows = [[f"Co{i}" for i in range(20)]]
        G, _ = self.build("Center", set(), papers, rows, 1, 5)
        self.assertEqual(G.number_of_nodes(), 6)

    def test_inter_coauthor_edges(self):
        rows = [["A", "B", "C"], ["A", "B", "D"]]
        G, _ = self.build("X", set(), {"A": 2, "B": 2, "C": 1, "D": 1}, rows, 2, 10)
        self.assertIn(("A", "B"), G.edges())
        self.assertEqual(G["A"]["B"]["weight"], 2)

    def test_center_attributes(self):
        G, _ = self.build("Alice", {"Alice"}, {"Bob": 1}, [["Alice", "Bob"]], 3, 10)
        self.assertEqual(G.nodes["Alice"]["papers"], 3)
        self.assertEqual(G.nodes["Alice"]["type"], "center")

    def test_coauthor_attributes(self):
        G, _ = self.build("Alice", {"Alice"}, {"Bob": 7}, [["Alice", "Bob"]], 3, 10)
        self.assertEqual(G.nodes["Bob"]["papers"], 7)
        self.assertEqual(G.nodes["Bob"]["type"], "coauthor")


class TestPlotlyNetworkGraph(unittest.TestCase):
    def setUp(self):
        self.render = m.plotly_network_graph

    def test_returns_figure(self):
        G = nx.Graph()
        G.add_node("cs.AI", count=100)
        G.add_node("math.AT", count=50)
        G.add_edge("cs.AI", "math.AT", weight=10)
        fig = self.render(G)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 2)

    def test_center_node(self):
        G = nx.Graph()
        G.add_node("Center", type="center", papers=100, size=50)
        fig = self.render(G)
        self.assertIsInstance(fig, go.Figure)

    def test_color_values(self):
        G = nx.Graph()
        G.add_node("A", count=100)
        G.add_node("B", count=50)
        G.add_edge("A", "B", weight=1)
        fig = self.render(G, color_values=[100, 50])
        self.assertIsInstance(fig, go.Figure)

    def test_color_map_callback(self):
        G = nx.Graph()
        G.add_node("A", count=100)
        G.add_node("B", count=50)
        G.add_edge("A", "B", weight=1)
        fig = self.render(G, node_color_map=lambda n, d: "#ff0000")
        self.assertIsInstance(fig, go.Figure)

    def test_empty_graph(self):
        fig = self.render(nx.Graph())
        self.assertIsInstance(fig, go.Figure)

    def test_large_graph(self):
        G = nx.Graph()
        for i in range(100):
            G.add_node(f"N{i}", count=i * 10)
            if i > 0:
                G.add_edge(f"N{i}", f"N{i - 1}", weight=i)
        fig = self.render(G)
        self.assertIsInstance(fig, go.Figure)


class TestLabels(unittest.TestCase):
    def test_known(self):
        self.assertEqual(
            labels.readable_category("cs.AI"),
            "Computer Science - Artificial Intelligence"
        )

    def test_unknown(self):
        self.assertEqual(
            labels.readable_category("nonexistent.XXX"),
            "nonexistent.XXX"
        )

    def test_multiple(self):
        r = labels.readable_categories("cs.AI math.AT")
        self.assertIn("Artificial Intelligence", r)
        self.assertIn("Algebraic Topology", r)
        self.assertIn("|", r)

    def test_column_name(self):
        self.assertEqual(
            labels.readable_column("authors_parsed"),
            "Authors (structured)"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
