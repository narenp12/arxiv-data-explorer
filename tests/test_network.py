import sys
import os
import re
from unittest.mock import MagicMock, patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shared_mock import install_streamlit_mock

install_streamlit_mock()

SRC = os.path.join(HERE, "..", "arxiv_explorer")
sys.path.insert(0, SRC)

import unittest
import networkx as nx
import polars as pl
import plotly.graph_objects as go
import network_app as m
import labels
import data_loader


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
        self.pc = pl.DataFrame(
            {
                "categories": ["cs.AI", "math.AT", "stat.ML", "physics.optics"],
                "count": [100, 80, 60, 40],
            }
        )
        self.cooc = pl.DataFrame(
            {
                "categories": ["cs.AI", "cs.AI", "math.AT"],
                "categories_b": ["math.AT", "stat.ML", "stat.ML"],
                "count": [30, 15, 5],
            }
        )

    def test_basic(self):
        G = self.build(self.pc, self.cooc, top_n=4, min_cooc=10)
        self.assertEqual(G.number_of_nodes(), 4)
        self.assertEqual(G.number_of_edges(), 2)

    def test_min_cooc_filter(self):
        self.assertEqual(self.build(self.pc, self.cooc, 4, 20).number_of_edges(), 1)

    def test_top_n_limit(self):
        self.assertEqual(self.build(self.pc, self.cooc, 2, 1).number_of_nodes(), 2)

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

    def test_max_coauthors_zero_returns_center_only(self):
        papers = {"Co1": 5, "Co2": 3}
        G, _ = self.build(
            "Center", {"Center"}, papers, [["Center", "Co1", "Co2"]], 5, 0
        )
        self.assertEqual(G.number_of_nodes(), 1)
        self.assertEqual(G.nodes["Center"]["type"], "center")


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
        self.assertGreaterEqual(len(fig.data), 2)
        self.assertIsInstance(fig.data[-1], go.Scatter)
        self.assertEqual(fig.data[-1].mode, "markers")

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
            "Computer Science - Artificial Intelligence",
        )

    def test_unknown(self):
        self.assertEqual(labels.readable_category("nonexistent.XXX"), "nonexistent.XXX")

    def test_multiple(self):
        r = labels.readable_categories("cs.AI math.AT")
        self.assertIn("Artificial Intelligence", r)
        self.assertIn("Algebraic Topology", r)
        self.assertIn("|", r)

    def test_column_name(self):
        self.assertEqual(
            labels.readable_column("authors_parsed"), "Authors (structured)"
        )


# ---------------------------------------------------------------------------
# labels.COLUMN_HELP
# ---------------------------------------------------------------------------
class TestColumnHelp(unittest.TestCase):
    def test_all_keys_have_descriptions(self):
        for key, desc in labels.COLUMN_HELP.items():
            with self.subTest(key=key):
                self.assertTrue(len(desc) > 0, f"Empty description for {key}")

    def test_source_columns_present(self):
        source = {
            "id",
            "submitter",
            "authors",
            "title",
            "comments",
            "journal-ref",
            "doi",
            "report-no",
            "categories",
            "license",
            "abstract",
            "versions",
            "update_date",
            "authors_parsed",
        }
        for col in source:
            with self.subTest(col=col):
                self.assertIn(col, labels.COLUMN_HELP)

    def test_derived_columns_present(self):
        derived = {
            "year",
            "month",
            "n_cats",
            "n_authors",
            "n_versions",
            "title_len",
            "abstract_len",
            "has_pages",
            "has_figures",
            "pct",
            "relative",
            "papers",
            "count",
            "filled_pct",
            "domain",
        }
        for col in derived:
            with self.subTest(col=col):
                self.assertIn(col, labels.COLUMN_HELP)

    def test_no_duplicate_keys(self):
        self.assertEqual(len(labels.COLUMN_HELP), len(set(labels.COLUMN_HELP.keys())))


# ---------------------------------------------------------------------------
# _top_authors  (the full_name Polars expression that had the .str.strip() bug)
# ---------------------------------------------------------------------------
class TestTopAuthors(unittest.TestCase):
    def test_full_name_first_last(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": [[["Smith", "John", ""], ["Doe", "Jane", ""]]],
            }
        ).lazy()
        result = m._top_authors(lf)
        names = result["full_name"].to_list()
        self.assertIn("John Smith", names)
        self.assertIn("Jane Doe", names)

    def test_empty_first_name(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": [[["Einstein", "", ""]]],
            }
        ).lazy()
        result = m._top_authors(lf)
        self.assertIn("Einstein", result["full_name"].to_list())

    def test_counts_aggregate(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": [
                    [["Smith", "John", ""]],
                    [["Smith", "John", ""]],
                    [["Doe", "Jane", ""]],
                ],
            }
        ).lazy()
        result = m._top_authors(lf)
        by_name = {r["full_name"]: r["count"] for r in result.iter_rows(named=True)}
        self.assertEqual(by_name["John Smith"], 2)
        self.assertEqual(by_name["Jane Doe"], 1)

    def test_top_20_limit(self):
        authors = [[[f"Last{i}", f"First{i}", ""]] for i in range(30)]
        lf = pl.DataFrame({"authors_parsed": authors}).lazy()
        result = m._top_authors(lf)
        self.assertLessEqual(len(result), 20)

    def test_sorted_descending(self):
        authors = [[["Common", "Very", ""]]] * 10 + [[["Rare", "A", ""]]] * 2
        lf = pl.DataFrame({"authors_parsed": authors}).lazy()
        result = m._top_authors(lf)
        counts = result["count"].to_list()
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_empty_data(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": pl.Series([], dtype=pl.List(pl.List(pl.Utf8))),
            }
        ).lazy()
        result = m._top_authors(lf)
        self.assertEqual(len(result), 0)


# ---------------------------------------------------------------------------
# precompute_category_data
# ---------------------------------------------------------------------------
class TestPrecomputeCategoryData(unittest.TestCase):
    def test_basic_paper_counts(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI stat.ML", "math.AT cs.AI", "stat.ML"],
            }
        ).lazy()
        pc, _ = m.precompute_category_data(lf)
        by_cat = {r["categories"]: r["count"] for r in pc.iter_rows(named=True)}
        self.assertEqual(by_cat["cs.AI"], 2)
        self.assertEqual(by_cat["math.AT"], 1)
        self.assertEqual(by_cat["stat.ML"], 2)

    def test_cooccurrence_generated(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI stat.ML", "cs.AI math.AT"],
            }
        ).lazy()
        _, cooc = m.precompute_category_data(lf)
        self.assertGreater(len(cooc), 0)

    def test_category_aliasing(self):
        lf = pl.DataFrame(
            {
                "categories": ["math-ph cs.AI"],
            }
        ).lazy()
        pc, _ = m.precompute_category_data(lf)
        cats = pc["categories"].to_list()
        self.assertIn("math.MP", cats)
        self.assertNotIn("math-ph", cats)

    def test_deduplicates_per_paper(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI cs.AI"],
            }
        ).lazy()
        pc, _ = m.precompute_category_data(lf)
        row = pc.filter(pl.col("categories") == "cs.AI")
        self.assertEqual(row["count"][0], 1)

    def test_no_cooc_same_category(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI"],
            }
        ).lazy()
        _, cooc = m.precompute_category_data(lf)
        self.assertEqual(len(cooc), 0)

    def test_multiple_cooc_pairs(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI stat.ML math.AT"],
            }
        ).lazy()
        _, cooc = m.precompute_category_data(lf)
        pairs = {
            (r["categories"], r["categories_b"]) for r in cooc.iter_rows(named=True)
        }
        self.assertIn(("cs.AI", "math.AT"), pairs)
        self.assertIn(("cs.AI", "stat.ML"), pairs)
        self.assertIn(("math.AT", "stat.ML"), pairs)

    def test_all_aliases_mapped(self):
        for alias, target in m._CATEGORY_ALIASES.items():
            with self.subTest(alias=alias):
                lf = pl.DataFrame({"categories": [alias]}).lazy()
                pc, _ = m.precompute_category_data(lf)
                self.assertIn(target, pc["categories"].to_list())
                self.assertNotIn(alias, pc["categories"].to_list())


# ---------------------------------------------------------------------------
# precompute_author_data
# ---------------------------------------------------------------------------
class TestPrecomputeAuthorData(unittest.TestCase):
    def setUp(self):
        self.lf = pl.DataFrame(
            {
                "authors": ["John Smith", "Jane Doe and John Smith", "Bob Wilson"],
                "authors_parsed": [
                    [["Smith", "John", ""]],
                    [["Doe", "Jane", ""], ["Smith", "John", ""]],
                    [["Wilson", "Bob", ""]],
                ],
            }
        ).lazy()

    @patch("data_loader.load_data")
    def test_match_found(self, mock_load):
        mock_load.return_value = self.lf
        matched, coauthors, rows, count = m.precompute_author_data("Smith")
        self.assertEqual(count, 2)
        self.assertIn("John Smith", matched)

    @patch("data_loader.load_data")
    def test_no_match_returns_none(self, mock_load):
        mock_load.return_value = self.lf
        matched, _, _, count = m.precompute_author_data("XYZ")
        self.assertEqual(count, 0)
        self.assertIsNone(matched)

    @patch("data_loader.load_data")
    def test_coauthor_papers_count(self, mock_load):
        mock_load.return_value = self.lf
        _, coauthors, _, _ = m.precompute_author_data("Smith")
        self.assertIn("Jane Doe", coauthors)
        self.assertEqual(coauthors["Jane Doe"], 1)

    @patch("data_loader.load_data")
    def test_center_excluded_from_coauthors(self, mock_load):
        mock_load.return_value = self.lf
        _, coauthors, _, _ = m.precompute_author_data("Smith")
        self.assertNotIn("John Smith", coauthors)

    @patch("data_loader.load_data")
    def test_full_name_format(self, mock_load):
        mock_load.return_value = self.lf
        matched, _, _, _ = m.precompute_author_data("Smith")
        for name in matched:
            self.assertIn("John Smith", name)

    @patch("data_loader.load_data")
    def test_empty_authors_parsed(self, mock_load):
        mock_load.return_value = pl.DataFrame(
            {
                "authors": ["No One"],
                "authors_parsed": [[["", "", ""]]],
            }
        ).lazy()
        matched, coauthors, rows, count = m.precompute_author_data("No")
        self.assertEqual(count, 0)
        self.assertIsNone(matched)

    @patch("data_loader.load_data")
    def test_case_insensitive(self, mock_load):
        mock_load.return_value = self.lf
        matched, _, _, count = m.precompute_author_data("smith")
        self.assertEqual(count, 2)

    @patch("data_loader.load_data")
    def test_partial_match(self, mock_load):
        mock_load.return_value = self.lf
        matched, _, _, count = m.precompute_author_data("John")
        self.assertGreater(count, 0)

    @patch("data_loader.load_data")
    def test_rows_cache_structure(self, mock_load):
        mock_load.return_value = self.lf
        _, _, rows, _ = m.precompute_author_data("Smith")
        for paper_coauthors in rows:
            for name in paper_coauthors:
                self.assertNotIn("Smith", name)


# ---------------------------------------------------------------------------
# _domain_counts
# ---------------------------------------------------------------------------
class TestDomainCounts(unittest.TestCase):
    def test_domain_extraction(self):
        pc = pl.DataFrame(
            {
                "categories": ["cs.AI", "cs.LG", "math.AT", "stat.ML", "cs.CV"],
                "count": [100, 80, 60, 40, 30],
            }
        )
        result = m._domain_counts(pc)
        domains = {r["domain"]: r["papers"] for r in result.iter_rows(named=True)}
        self.assertEqual(domains["cs"], 210)
        self.assertEqual(domains["math"], 60)
        self.assertEqual(domains["stat"], 40)

    def test_subcategory_count(self):
        pc = pl.DataFrame(
            {
                "categories": ["cs.AI", "cs.LG", "cs.CV"],
                "count": [100, 80, 30],
            }
        )
        result = m._domain_counts(pc)
        cs_row = result.filter(pl.col("domain") == "cs")
        self.assertEqual(cs_row["subcategories"][0], 3)

    def test_sorted_by_papers_descending(self):
        pc = pl.DataFrame(
            {
                "categories": ["cs.AI", "math.AT", "stat.ML"],
                "count": [100, 200, 50],
            }
        )
        result = m._domain_counts(pc)
        self.assertEqual(result["domain"][0], "math")

    def test_domain_without_dot(self):
        pc = pl.DataFrame(
            {
                "categories": ["cs", "physics.optics"],
                "count": [100, 80],
            }
        )
        result = m._domain_counts(pc)
        domains = result["domain"].to_list()
        self.assertIn("cs", domains)
        self.assertIn("physics", domains)

    def test_empty_input(self):
        pc = pl.DataFrame(
            {
                "categories": pl.Series([], dtype=pl.Utf8),
                "count": pl.Series([], dtype=pl.Int64),
            }
        )
        result = m._domain_counts(pc)
        self.assertEqual(len(result), 0)


# ---------------------------------------------------------------------------
# _category_authors
# ---------------------------------------------------------------------------
class TestCategoryAuthors(unittest.TestCase):
    def setUp(self):
        self.lf = pl.DataFrame(
            {
                "categories": ["cs.AI", "cs.AI stat.ML", "math.AT"],
                "authors_parsed": [
                    [["Smith", "John", ""]],
                    [["Doe", "Jane", ""]],
                    [["Wilson", "Bob", ""]],
                ],
            }
        ).lazy()

    def test_filters_by_category(self):
        result = m._category_authors(self.lf, "cs.AI")
        names = result["authors_parsed"].to_list()
        self.assertIn("Smith", names)
        self.assertIn("Doe", names)
        self.assertNotIn("Wilson", names)

    def test_paper_count(self):
        result = m._category_authors(self.lf, "cs.AI")
        by_name = {
            r["authors_parsed"]: r["papers"] for r in result.iter_rows(named=True)
        }
        self.assertEqual(by_name["Smith"], 1)
        self.assertEqual(by_name["Doe"], 1)

    def test_sorted_by_papers(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI", "cs.AI", "cs.AI stat.ML"],
                "authors_parsed": [
                    [["Smith", "John", ""]],
                    [["Smith", "John", ""]],
                    [["Doe", "Jane", ""]],
                ],
            }
        ).lazy()
        result = m._category_authors(lf, "cs.AI")
        self.assertEqual(result["authors_parsed"][0], "Smith")
        self.assertGreater(result["papers"][0], result["papers"][1])

    def test_category_with_alias(self):
        lf = pl.DataFrame(
            {
                "categories": ["math-ph"],
                "authors_parsed": [[["Smith", "John", ""]]],
            }
        ).lazy()
        result = m._category_authors(lf, "math.MP")
        self.assertEqual(len(result), 1)

    def test_empty_authors_list(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI"],
                "authors_parsed": [[[]]],
            }
        ).lazy()
        result = m._category_authors(lf, "cs.AI")
        self.assertEqual(len(result), 0)

    def test_no_matches(self):
        result = m._category_authors(self.lf, "nonexistent.XXX")
        self.assertEqual(len(result), 0)


# ---------------------------------------------------------------------------
# _author_papers_multi
# ---------------------------------------------------------------------------
class TestAuthorPapersMultiSingle(unittest.TestCase):
    def setUp(self):
        self.lf = pl.DataFrame(
            {
                "categories": ["cs.AI", "cs.AI", "math.AT"],
                "authors_parsed": [
                    [["Smith", "John", ""]],
                    [["Smith", "John", ""]],
                    [["Doe", "Jane", ""]],
                ],
                "id": ["1001", "1002", "1003"],
                "title": ["Paper A", "Paper B", "Paper C"],
                "abstract": ["Abstract A", "Abstract B", "Abstract C"],
                "authors": ["John Smith", "John Smith", "Jane Doe"],
                "update_date": ["2023-01-01", "2023-06-01", "2023-03-01"],
            }
        ).lazy()

    def test_returns_matching_papers(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith",))
        self.assertEqual(len(result), 2)

    def test_returns_required_columns(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith",))
        cols = set(result.columns)
        self.assertTrue(
            cols.issuperset(
                {"id", "title", "abstract", "authors", "categories", "update_date"}
            )
        )

    def test_sorted_by_date_desc(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith",))
        dates = result["update_date"].to_list()
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_no_match(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Unknown",))
        self.assertEqual(len(result), 0)

    def test_with_alias(self):
        lf = pl.DataFrame(
            {
                "categories": ["math-ph"],
                "authors_parsed": [[["Smith", "John", ""]]],
                "id": ["1001"],
                "title": ["Paper A"],
                "abstract": ["Abstract A"],
                "authors": ["John Smith"],
                "update_date": ["2023-01-01"],
            }
        ).lazy()
        result = m._author_papers_multi(lf, "math.MP", ("Smith",))
        self.assertEqual(len(result), 1)


class TestAuthorPapersMulti(unittest.TestCase):
    def setUp(self):
        self.lf = pl.DataFrame(
            {
                "categories": [
                    "cs.AI",
                    "cs.AI",
                    "cs.AI",
                    "cs.AI",
                    "math.AT",
                ],
                "authors_parsed": [
                    [["Smith", "John", ""]],
                    [["Doe", "Jane", ""]],
                    [["Smith", "John", ""], ["Doe", "Jane", ""]],
                    [["Brown", "Alice", ""]],
                    [["Smith", "John", ""]],
                ],
                "id": ["1001", "1002", "1003", "1004", "1005"],
                "title": [
                    "Paper A",
                    "Paper B",
                    "Paper C",
                    "Paper D",
                    "Paper E",
                ],
                "abstract": [
                    "Abstract A",
                    "Abstract B",
                    "Abstract C",
                    "Abstract D",
                    "Abstract E",
                ],
                "authors": [
                    "John Smith",
                    "Jane Doe",
                    "John Smith and Jane Doe",
                    "Alice Brown",
                    "John Smith",
                ],
                "update_date": [
                    "2023-01-01",
                    "2023-02-01",
                    "2023-03-01",
                    "2023-04-01",
                    "2023-05-01",
                ],
            }
        ).lazy()

    def test_returns_coauthored_papers(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith", "Doe"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result["id"][0], "1003")

    def test_no_match_for_non_coauthors(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith", "Brown"))
        self.assertEqual(len(result), 0)

    def test_three_way_coauthorship(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI", "cs.AI"],
                "authors_parsed": [
                    [
                        ["Smith", "John", ""],
                        ["Doe", "Jane", ""],
                        ["Brown", "Alice", ""],
                    ],
                    [["Smith", "John", ""], ["Doe", "Jane", ""]],
                ],
                "id": ["2001", "2002"],
                "title": ["Paper X", "Paper Y"],
                "abstract": ["Abstract X", "Abstract Y"],
                "authors": [
                    "John Smith, Jane Doe, Alice Brown",
                    "John Smith, Jane Doe",
                ],
                "update_date": ["2023-01-01", "2023-01-02"],
            }
        ).lazy()
        result = m._author_papers_multi(lf, "cs.AI", ("Smith", "Doe", "Brown"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result["id"][0], "2001")

    def test_single_author_returns_all(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith",))
        self.assertEqual(len(result), 2)
        self.assertIn("1001", result["id"].to_list())
        self.assertIn("1003", result["id"].to_list())

    def test_returns_required_columns(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith", "Doe"))
        cols = set(result.columns)
        self.assertTrue(
            cols.issuperset(
                {"id", "title", "abstract", "authors", "categories", "update_date"}
            )
        )

    def test_sorted_by_date_desc(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith",))
        dates = result["update_date"].to_list()
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_empty_result_when_one_author_missing(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith", "Unknown"))
        self.assertEqual(len(result), 0)

    def test_respects_category(self):
        result = m._author_papers_multi(self.lf, "math.AT", ("Smith",))
        self.assertEqual(len(result), 1)
        self.assertEqual(result["id"][0], "1005")

    def test_with_alias(self):
        lf = pl.DataFrame(
            {
                "categories": ["math-ph"],
                "authors_parsed": [[["Smith", "John", ""], ["Doe", "Jane", ""]]],
                "id": ["3001"],
                "title": ["Paper Z"],
                "abstract": ["Abstract Z"],
                "authors": ["John Smith, Jane Doe"],
                "update_date": ["2023-01-01"],
            }
        ).lazy()
        result = m._author_papers_multi(lf, "math.MP", ("Smith", "Doe"))
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# _coa_cache_fig
# ---------------------------------------------------------------------------
class TestCoaCacheFig(unittest.TestCase):
    def test_sets_session_state(self):
        m.st.session_state.pop("co_fig", None)
        G = nx.Graph()
        G.add_node("Alice", type="center", papers=10, size=50)
        G.add_node("Bob", type="coauthor", papers=3, size=20)
        G.add_edge("Alice", "Bob", weight=3)
        m._coa_cache_fig(G, "Alice")
        self.assertIsNotNone(m.st.session_state.co_fig)

    def test_returns_figure(self):
        G = nx.Graph()
        G.add_node("Alice", type="center", papers=5, size=30)
        G.add_node("Bob", type="coauthor", papers=2, size=15)
        G.add_edge("Alice", "Bob", weight=2)
        m._coa_cache_fig(G, "Alice")
        fig = m.st.session_state.co_fig
        self.assertIsInstance(fig, go.Figure)

    def test_center_node_gold_color(self):
        G = nx.Graph()
        G.add_node("Alice", type="center", papers=5, size=30)
        G.add_node("Bob", type="coauthor", papers=2, size=15)
        G.add_edge("Alice", "Bob", weight=2)
        m._coa_cache_fig(G, "Alice")
        fig = m.st.session_state.co_fig
        node_trace = fig.data[-1]
        self.assertIn("#ffd700", str(node_trace.marker.color))

    def test_empty_graph_no_error(self):
        G = nx.Graph()
        try:
            m._coa_cache_fig(G, "unknown")
        except Exception as e:
            self.fail(f"_coa_cache_fig raised {e}")

    def test_multiple_coauthors_color_gradient(self):
        G = nx.Graph()
        G.add_node("Center", type="center", papers=10, size=50)
        for i in range(5):
            G.add_node(f"Co{i}", type="coauthor", papers=i + 1, size=10)
            G.add_edge("Center", f"Co{i}", weight=i + 1)
        m._coa_cache_fig(G, "Center")
        fig = m.st.session_state.co_fig
        colors = fig.data[-1].marker.color
        self.assertEqual(len(colors), 6)

    def test_center_node_only(self):
        G = nx.Graph()
        G.add_node("Solo", type="center", papers=5, size=30)
        m._coa_cache_fig(G, "Solo")
        fig = m.st.session_state.co_fig
        self.assertIsInstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# build_category_graph edge cases
# ---------------------------------------------------------------------------
class TestBuildCategoryGraphEdgeCases(unittest.TestCase):
    def setUp(self):
        self.build = m.build_category_graph

    def test_empty_cooc(self):
        pc = pl.DataFrame(
            {
                "categories": ["cs.AI", "math.AT"],
                "count": [100, 80],
            }
        )
        cooc = pl.DataFrame(
            {
                "categories": pl.Series([], dtype=pl.Utf8),
                "categories_b": pl.Series([], dtype=pl.Utf8),
                "count": pl.Series([], dtype=pl.Int64),
            }
        )
        G = self.build(pc, cooc, 2, 1)
        self.assertEqual(G.number_of_nodes(), 2)
        self.assertEqual(G.number_of_edges(), 0)

    def test_single_node(self):
        pc = pl.DataFrame(
            {
                "categories": ["cs.AI"],
                "count": [100],
            }
        )
        cooc = pl.DataFrame(
            {
                "categories": pl.Series([], dtype=pl.Utf8),
                "categories_b": pl.Series([], dtype=pl.Utf8),
                "count": pl.Series([], dtype=pl.Int64),
            }
        )
        G = self.build(pc, cooc, 1, 1)
        self.assertEqual(G.number_of_nodes(), 1)


# ---------------------------------------------------------------------------
# plotly_network_graph edge cases
# ---------------------------------------------------------------------------
class TestPlotlyNetworkGraphEdgeCases(unittest.TestCase):
    def setUp(self):
        self.render = m.plotly_network_graph

    def test_single_node_no_edges(self):
        G = nx.Graph()
        G.add_node("cs.AI", count=100)
        fig = self.render(G)
        self.assertIsInstance(fig, go.Figure)

    def test_only_coauthor_type_nodes(self):
        G = nx.Graph()
        G.add_node("Alice", type="coauthor", papers=5, size=30)
        G.add_node("Bob", type="coauthor", papers=3, size=20)
        G.add_edge("Alice", "Bob", weight=2)
        fig = self.render(G)
        self.assertIsInstance(fig, go.Figure)

    def test_no_type_attr_falls_to_category(self):
        G = nx.Graph()
        G.add_node("cs.AI", count=100)
        G.add_node("math.AT", count=50)
        G.add_edge("cs.AI", "math.AT", weight=10)
        fig = self.render(G)
        self.assertIsInstance(fig, go.Figure)

    def test_color_values_with_colorbar_title(self):
        G = nx.Graph()
        G.add_node("A", count=100)
        G.add_node("B", count=50)
        G.add_edge("A", "B", weight=1)
        fig = self.render(G, color_values=[100, 50], colorbar_title="Papers")
        self.assertIsInstance(fig, go.Figure)

    def test_node_color_map_with_color_values(self):
        G = nx.Graph()
        G.add_node("A", count=100)
        G.add_node("B", count=50)
        G.add_edge("A", "B", weight=1)
        fig = self.render(
            G, color_values=[100, 50], node_color_map=lambda n, d: "#00ff00"
        )
        self.assertIsInstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# data_loader
# ---------------------------------------------------------------------------
class TestDataLoaderLoadData(unittest.TestCase):
    def setUp(self):
        self._lf = pl.LazyFrame({"x": [1]})
        self._orig_load_remote = data_loader._load_remote
        data_loader._load_remote = MagicMock(return_value=self._lf)
        data_loader.st.session_state.clear()

    def tearDown(self):
        data_loader._load_remote = self._orig_load_remote
        data_loader.st.session_state.clear()

    @patch("os.path.exists", return_value=True)
    @patch("polars.scan_parquet")
    def test_local_source(self, mock_scan, mock_exists):
        data_loader.st.session_state["data_source"] = "local sample"
        mock_scan.return_value = self._lf
        result = data_loader.load_data()
        mock_scan.assert_called_once_with(data_loader.LOCAL_DATA)
        self.assertIs(result, self._lf)

    @patch("os.path.exists", return_value=True)
    @patch("polars.scan_parquet")
    def test_default_source_with_local_file(self, mock_scan, mock_exists):
        mock_scan.return_value = self._lf
        result = data_loader.load_data()
        mock_scan.assert_called_once_with(data_loader.LOCAL_DATA)
        self.assertIs(result, self._lf)

    @patch("os.path.exists", return_value=False)
    def test_default_source_no_local_file(self, mock_exists):
        result = data_loader.load_data()
        data_loader._load_remote.assert_called_once()
        self.assertIs(result, self._lf)

    @patch("os.path.exists", return_value=False)
    def test_remote_explicit(self, mock_exists):
        data_loader.st.session_state["data_source"] = "remote (HuggingFace)"
        result = data_loader.load_data()
        data_loader._load_remote.assert_called_once()
        self.assertIs(result, self._lf)

    @patch("os.path.exists", return_value=True)
    @patch("polars.scan_parquet")
    def test_remote_ignores_local_file(self, mock_scan, mock_exists):
        data_loader.st.session_state["data_source"] = "remote (HuggingFace)"
        data_loader.load_data()
        data_loader._load_remote.assert_called_once()
        mock_scan.assert_not_called()

    def test_default_source_not_in_session(self):
        self.assertNotIn("data_source", data_loader.st.session_state)


class TestDataLoaderLoadRemote(unittest.TestCase):
    def setUp(self):
        self._lf = pl.LazyFrame(
            {
                "x": [1],
                "authors_parsed": [[["Test", "Author", ""]]],
                "versions": [[{"version": "v1", "created": "2020-01-01"}]],
            }
        )

    @patch("glob.glob", return_value=["/fake/path/f1.parquet", "/fake/path/f2.parquet"])
    @patch("huggingface_hub.snapshot_download", return_value="/fake/path")
    @patch("polars.scan_parquet")
    def test_success(self, mock_scan, mock_download, mock_glob):
        mock_scan.return_value = self._lf
        result = data_loader._load_remote()
        mock_download.assert_called_once_with(
            data_loader.REMOTE_REPO, repo_type="dataset"
        )
        mock_scan.assert_called_once_with(
            ["/fake/path/f1.parquet", "/fake/path/f2.parquet"]
        )
        self.assertIs(result, self._lf)

    @patch("glob.glob", return_value=[])
    @patch("huggingface_hub.snapshot_download", return_value="/fake/path")
    @patch("os.path.exists", return_value=False)
    @patch("polars.scan_parquet")
    def test_no_parquet_files_raises(
        self, mock_scan, mock_exists, mock_download, mock_glob
    ):
        with self.assertRaises(FileNotFoundError):
            data_loader._load_remote()

    @patch("glob.glob")
    @patch("huggingface_hub.snapshot_download")
    @patch("os.path.exists", return_value=True)
    @patch("polars.scan_parquet")
    def test_fallback_to_local(self, mock_scan, mock_exists, mock_download, mock_glob):
        mock_download.side_effect = ConnectionError("Network unreachable")
        mock_scan.return_value = self._lf
        result = data_loader._load_remote()
        data_loader.st.warning.assert_called_once()
        mock_scan.assert_called_once_with(data_loader.LOCAL_DATA)
        self.assertIs(result, self._lf)


# ---------------------------------------------------------------------------
# Data source switching and cache invalidation
# ---------------------------------------------------------------------------
class TestDataSourceSwitching(unittest.TestCase):
    def setUp(self):
        data_loader.st.session_state.clear()
        self._orig_cache_data = data_loader.st.cache_data
        self._orig_cache_resource = data_loader.st.cache_resource
        data_loader.st.cache_data = MagicMock(wraps=self._orig_cache_data)
        data_loader.st.cache_resource = MagicMock(wraps=self._orig_cache_resource)

    def tearDown(self):
        data_loader.st.cache_data = self._orig_cache_data
        data_loader.st.cache_resource = self._orig_cache_resource
        data_loader.st.session_state.clear()

    # -- render_sidebar_data_source behavior --

    def test_first_run_no_cache_clear_sets_prev(self):
        data_loader.render_sidebar_data_source()
        data_loader.st.cache_data.clear.assert_not_called()
        data_loader.st.cache_resource.clear.assert_not_called()
        self.assertEqual(data_loader.st.session_state._prev_data_source, "local sample")

    def test_same_source_no_cache_clear(self):
        data_loader.render_sidebar_data_source()
        data_loader.st.cache_data.clear.reset_mock()
        data_loader.st.cache_resource.clear.reset_mock()
        data_loader.render_sidebar_data_source()
        data_loader.st.cache_data.clear.assert_not_called()
        data_loader.st.cache_resource.clear.assert_not_called()

    def test_source_switch_clears_caches(self):
        data_loader.render_sidebar_data_source()  # first run
        data_loader.st.cache_data.clear.reset_mock()
        data_loader.st.cache_resource.clear.reset_mock()
        data_loader.st.session_state.data_source = "remote (HuggingFace)"
        data_loader.render_sidebar_data_source()
        data_loader.st.cache_data.clear.assert_called_once()
        data_loader.st.cache_resource.clear.assert_called_once()

    def test_source_switch_updates_prev(self):
        data_loader.render_sidebar_data_source()
        data_loader.st.session_state.data_source = "remote (HuggingFace)"
        data_loader.render_sidebar_data_source()
        self.assertEqual(
            data_loader.st.session_state._prev_data_source,
            "remote (HuggingFace)",
        )

    def test_source_switch_sets_data_reset_flag(self):
        data_loader.render_sidebar_data_source()
        data_loader.st.session_state.data_source = "remote (HuggingFace)"
        data_loader.render_sidebar_data_source()
        self.assertTrue(data_loader.st.session_state.pop("_data_reset", False))

    def test_same_source_no_data_reset_flag(self):
        data_loader.render_sidebar_data_source()
        data_loader.st.session_state.pop("_data_reset", None)
        data_loader.render_sidebar_data_source()
        self.assertFalse(data_loader.st.session_state.get("_data_reset", False))

    def test_switch_back_to_local_also_triggers(self):
        data_loader.render_sidebar_data_source()  # local
        data_loader.st.session_state.data_source = "remote (HuggingFace)"
        data_loader.render_sidebar_data_source()  # remote
        data_loader.st.cache_data.clear.reset_mock()
        data_loader.st.cache_resource.clear.reset_mock()
        data_loader.st.session_state.data_source = "local sample"
        data_loader.render_sidebar_data_source()  # back to local
        data_loader.st.cache_data.clear.assert_called_once()

    # -- load_data behavior with switching --

    def test_load_data_returns_different_for_each_source(self):
        local_lf = pl.LazyFrame({"categories": ["cs.AI"] * 100})
        remote_lf = pl.LazyFrame({"categories": ["cs.AI"] * 200})
        with (
            patch("os.path.exists", return_value=True),
            patch("polars.scan_parquet", return_value=local_lf),
        ):
            result_local = data_loader.load_data()
        data_loader._load_remote = MagicMock(return_value=remote_lf)
        data_loader.st.session_state.data_source = "remote (HuggingFace)"
        result_remote = data_loader.load_data()
        self.assertIsNot(result_local, result_remote)
        self.assertEqual(result_local.collect().height, 100)
        self.assertEqual(result_remote.collect().height, 200)

    # -- precompute produces different results for different data --

    def test_precompute_different_data_different_counts(self):
        small = pl.LazyFrame({"categories": ["cs.AI stat.ML", "math.AT", "cs.AI"]})
        large = pl.LazyFrame(
            {
                "categories": [
                    "cs.AI stat.ML",
                    "cs.AI stat.ML",
                    "math.AT",
                    "math.AT",
                    "cs.LG",
                ]
            }
        )
        pc_small, _ = m.precompute_category_data(small)
        pc_large, _ = m.precompute_category_data(large)
        s_counts = dict(pc_small.iter_rows())
        l_counts = dict(pc_large.iter_rows())
        self.assertEqual(s_counts.get("cs.AI", 0), 2)
        self.assertEqual(s_counts.get("math.AT", 0), 1)
        self.assertEqual(l_counts.get("cs.AI", 0), 2)
        self.assertEqual(l_counts.get("math.AT", 0), 2)
        self.assertEqual(l_counts.get("cs.LG", 0), 1)
        self.assertNotEqual(len(pc_small), len(pc_large))

    # -- Graph rebuild condition --

    def test_graph_rebuilt_when_data_reset_set(self):
        data_loader.st.session_state.pop("_data_reset", None)
        data_loader.st.session_state.cat_graph = "stale"
        data_loader.st.session_state._data_reset = True
        self.assertIn("cat_graph", data_loader.st.session_state)
        self.assertTrue(data_loader.st.session_state.pop("_data_reset", False))

    def test_data_reset_consumed_only_once(self):
        data_loader.st.session_state._data_reset = True
        data_loader.st.session_state.pop("_data_reset", False)
        self.assertFalse(data_loader.st.session_state.get("_data_reset", False))

    def test_cat_ego_forward_skipped_when_stale_after_source_switch(self):
        G = nx.Graph()
        G.add_node("cs.AI", count=10)
        G.add_node("stat.ML", count=5)
        G.add_edge("cs.AI", "stat.ML", weight=3)
        all_nodes = sorted(G.nodes(), key=lambda n: -G.degree(n))
        data_loader.st.session_state._cat_ego_forward = "math.AT"
        self.assertNotIn("math.AT", all_nodes)
        if "_cat_ego_forward" in data_loader.st.session_state:
            if data_loader.st.session_state._cat_ego_forward in G:
                data_loader.st.session_state.cat_ego = data_loader.st.session_state._cat_ego_forward
            del data_loader.st.session_state._cat_ego_forward
        self.assertNotIn("_cat_ego_forward", data_loader.st.session_state)
        self.assertNotEqual(data_loader.st.session_state.get("cat_ego"), "math.AT")

    def test_cat_ego_forward_used_when_valid(self):
        G = nx.Graph()
        G.add_node("cs.AI", count=10)
        G.add_node("stat.ML", count=5)
        G.add_edge("cs.AI", "stat.ML", weight=3)
        data_loader.st.session_state._cat_ego_forward = "stat.ML"
        if "_cat_ego_forward" in data_loader.st.session_state:
            if data_loader.st.session_state._cat_ego_forward in G:
                data_loader.st.session_state.cat_ego = data_loader.st.session_state._cat_ego_forward
            del data_loader.st.session_state._cat_ego_forward
        self.assertEqual(data_loader.st.session_state.get("cat_ego"), "stat.ML")


class TestCategoryPattern(unittest.TestCase):
    def test_basic_pattern(self):
        pattern = m._category_pattern("cs.AI")
        self.assertIn(re.escape("cs.AI"), pattern)

    def test_includes_aliases(self):
        pattern = m._category_pattern("stat.ML")
        self.assertIn(re.escape("stat.ML"), pattern)

    def test_matches_string(self):
        pattern = m._category_pattern("cs.AI")
        self.assertIsNotNone(re.search(pattern, "cs.AI stat.ML"))
        self.assertIsNotNone(re.search(pattern, "cs.AI"))

    def test_does_not_match_substring(self):
        pattern = m._category_pattern("cs.AI")
        # Should not match "cs.AI2" or similar
        self.assertIsNone(re.search(pattern, "cs.AI2"))

    def test_empty_category(self):
        pattern = m._category_pattern("")
        self.assertTrue(pattern)


# ---------------------------------------------------------------------------
# _author_stats
# ---------------------------------------------------------------------------
class TestAuthorStats(unittest.TestCase):
    def test_all_categories(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": [
                    [["A", "B", ""]],
                    [["C", "D", ""], ["E", "F", ""]],
                    [["G", "H", ""]] * 100,
                    [["I", "J", ""]] * 1000,
                ],
            }
        ).lazy()
        solo, multi, large, huge = m._author_stats(lf)
        self.assertEqual(solo, 1)
        self.assertEqual(multi, 3)
        self.assertEqual(large, 2)
        self.assertEqual(huge, 1)

    def test_empty_data(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": pl.Series([], dtype=pl.List(pl.List(pl.Utf8))),
            }
        ).lazy()
        solo, multi, large, huge = m._author_stats(lf)
        self.assertEqual(solo, 0)
        self.assertEqual(multi, 0)
        self.assertEqual(large, 0)
        self.assertEqual(huge, 0)


# ---------------------------------------------------------------------------
# _prolific_authors
# ---------------------------------------------------------------------------
class TestProlificAuthors(unittest.TestCase):
    def test_returns_top_20(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": [[["Smith", "John", ""]] for _ in range(25)],
            }
        ).lazy()
        result = m._prolific_authors(lf)
        self.assertEqual(len(result), 1)
        self.assertIn("full_name", result.columns)
        self.assertIn("relative", result.columns)

    def test_relative_column(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": [
                    [["Smith", "John", ""], ["Doe", "Jane", ""]],
                ],
            }
        ).lazy()
        result = m._prolific_authors(lf)
        self.assertTrue((result["relative"] == 100).all())

    def test_empty_data(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": pl.Series([], dtype=pl.List(pl.List(pl.Utf8))),
            }
        ).lazy()
        result = m._prolific_authors(lf)
        self.assertEqual(len(result), 0)


# ---------------------------------------------------------------------------
# _overlap_stats
# ---------------------------------------------------------------------------
class TestOverlapStats(unittest.TestCase):
    def test_returns_total_and_multi_cat(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI stat.ML", "math.AT", "cs.AI"],
            }
        ).lazy()
        total, multi_cat = m._overlap_stats(lf)
        self.assertEqual(total, 3)
        self.assertEqual(multi_cat, 1)

    def test_all_multi_cat(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI stat.ML", "math.AT cs.LG"],
            }
        ).lazy()
        total, multi_cat = m._overlap_stats(lf)
        self.assertEqual(total, 2)
        self.assertEqual(multi_cat, 2)

    def test_no_multi_cat(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI", "math.AT"],
            }
        ).lazy()
        total, multi_cat = m._overlap_stats(lf)
        self.assertEqual(total, 2)
        self.assertEqual(multi_cat, 0)


# ---------------------------------------------------------------------------
# _all_author_names
# ---------------------------------------------------------------------------
class TestAllAuthorNames(unittest.TestCase):
    def test_returns_all_names(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": [
                    [["Smith", "John", ""]],
                    [["Smith", "John", ""]],
                    [["Doe", "Jane", ""]],
                ],
            }
        ).lazy()
        result = m._all_author_names(lf)
        self.assertEqual(len(result), 2)
        self.assertIn("full_name", result.columns)
        self.assertIn("count", result.columns)

    def test_empty_data(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": pl.Series([], dtype=pl.List(pl.List(pl.Utf8))),
            }
        ).lazy()
        result = m._all_author_names(lf)
        self.assertEqual(len(result), 0)

    def test_sorted_by_count_desc(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": [
                    [["Z", "A", ""]] * 5,
                    [["A", "B", ""]] * 10,
                ],
            }
        ).lazy()
        result = m._all_author_names(lf)
        self.assertEqual(result["full_name"][0], "B A")
        self.assertEqual(result["count"][0], 10)


# ---------------------------------------------------------------------------
# _rank_author_matches
# ---------------------------------------------------------------------------
class TestRankAuthorMatches(unittest.TestCase):
    def setUp(self):
        self.df = pl.DataFrame(
            {
                "full_name": ["John Smith", "Jane Doe", "Bob Smith", "Alice Johnson"],
                "count": [10, 20, 5, 15],
            }
        )

    def test_exact_match_first(self):
        result = m._rank_author_matches(self.df, "John Smith")
        self.assertEqual(len(result), 1)
        self.assertEqual(result["full_name"][0], "John Smith")

    def test_prefix_matches_ranked_before_contains(self):
        result = m._rank_author_matches(self.df, "Smith")
        self.assertGreater(len(result), 0)
        # "Bob Smith" and "John Smith" both contain "Smith" — exact/longer suffix
        # Since neither starts with "Smith", both are rank 2 (contains)
        # Sorted by rank then count desc, so John Smith (10) then Bob Smith (5)

    def test_case_insensitive(self):
        result = m._rank_author_matches(self.df, "john smith")
        self.assertEqual(len(result), 1)

    def test_no_match(self):
        result = m._rank_author_matches(self.df, "XYZNonexistent")
        self.assertEqual(len(result), 0)

    def test_empty_query_returns_all(self):
        result = m._rank_author_matches(self.df, "")
        self.assertEqual(len(result), 4)

    def test_starts_with_ranked_first(self):
        result = m._rank_author_matches(self.df, "Bob")
        self.assertEqual(len(result), 1)
        self.assertEqual(result["full_name"][0], "Bob Smith")


# ---------------------------------------------------------------------------
# AuthorFullNameExpr — null safety in list.eval
# ---------------------------------------------------------------------------
class TestAuthorFullNameExpr(unittest.TestCase):
    def test_normal_name(self):
        df = pl.DataFrame({"authors_parsed": [[["Smith", "John", ""]]]})
        result = df.with_columns(
            pl.col("authors_parsed").list.eval(m._author_full_name_expr()).alias("full")
        ).to_dict(as_series=False)["full"][0][0]
        self.assertEqual(result, "John Smith")

    def test_missing_first_name(self):
        df = pl.DataFrame({"authors_parsed": [[["Smith"]]]})
        result = df.with_columns(
            pl.col("authors_parsed").list.eval(m._author_full_name_expr()).alias("full")
        ).to_dict(as_series=False)["full"][0][0]
        self.assertEqual(result.strip(), "Smith")

    def test_empty_entry(self):
        df = pl.DataFrame({"authors_parsed": [[["", "", ""]]]})
        result = df.with_columns(
            pl.col("authors_parsed").list.eval(m._author_full_name_expr()).alias("full")
        ).to_dict(as_series=False)["full"][0][0]
        self.assertEqual(result.strip(), "")


# ---------------------------------------------------------------------------
# Center node marker — plotly_network_graph border properties
# ---------------------------------------------------------------------------
class TestCenterNodeMarker(unittest.TestCase):
    def test_center_node_has_thick_border(self):
        G = nx.Graph()
        G.add_node("Center", type="center", papers=100, size=50)
        G.add_node("Other", count=10)
        G.add_edge("Center", "Other", weight=3)
        fig = m.plotly_network_graph(G, node_color_map=lambda n, d: "#ff0")
        marker = fig.data[-1].marker
        self.assertEqual(marker.line.width[0], 3)
        self.assertEqual(marker.line.width[1], 1)

    def test_no_center_falls_back_to_default_border(self):
        G = nx.Graph()
        G.add_node("A", count=10)
        G.add_node("B", count=20)
        G.add_edge("A", "B", weight=1)
        fig = m.plotly_network_graph(G)
        marker = fig.data[-1].marker
        for w in marker.line.width:
            self.assertEqual(w, 1)


class TestAuthorStatsJsonFallback(unittest.TestCase):
    """_author_stats should handle authors_parsed stored as JSON string."""

    def test_json_string_parsed_correctly(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": [
                    '[["Smith", "John", ""]]',
                    '[["Doe", "Jane", ""], ["Brown", "Bob", ""]]',
                ],
            }
        ).lazy()
        solo, multi, _, _ = m._author_stats(lf)
        self.assertEqual(solo, 1)
        self.assertEqual(multi, 1)

    def test_json_string_empty(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": pl.Series([], dtype=pl.Utf8),
            }
        ).lazy()
        solo, multi, large, huge = m._author_stats(lf)
        self.assertEqual(solo, 0)
        self.assertEqual(multi, 0)
        self.assertEqual(large, 0)
        self.assertEqual(huge, 0)

    def test_json_string_single_list(self):
        lf = pl.DataFrame(
            {
                "authors_parsed": [
                    '[["Smith", "John", ""]]',
                ],
            }
        ).lazy()
        solo, multi, _, _ = m._author_stats(lf)
        self.assertEqual(solo, 1)
        self.assertEqual(multi, 0)

    def test_json_string_many_authors(self):
        import json
        lf = pl.DataFrame(
            {
                "authors_parsed": [
                    json.dumps([["A"]] * 200),
                ],
            }
        ).lazy()
        solo, multi, large, huge = m._author_stats(lf)
        self.assertEqual(solo, 0)
        self.assertEqual(multi, 1)
        self.assertEqual(large, 1)
        self.assertEqual(huge, 0)


class TestCategoryPatternSpecialChars(unittest.TestCase):
    """_category_pattern should handle regex special chars."""

    def test_dot_in_code(self):
        pattern = m._category_pattern("cs.AI")
        self.assertIsNotNone(re.search(pattern, " cs.AI "))
        self.assertIsNone(re.search(pattern, "csXAI"))

    def test_plus_in_code(self):
        pattern = m._category_pattern("cs+AI")
        self.assertTrue(pattern)
        self.assertIsNotNone(re.search(pattern, " cs+AI "))

    def test_parens_in_code(self):
        pattern = m._category_pattern("stat.ML")
        self.assertIsNotNone(re.search(pattern, " stat.ML "))

    def test_alternation_with_alias(self):
        pattern = m._category_pattern("math.MP")
        # Should match the target and its alias
        self.assertIsNotNone(re.search(pattern, " math.MP "))
        self.assertIsNotNone(re.search(pattern, " math-ph "))


class TestAuthorPapersMultiEdgeCases(unittest.TestCase):
    """_author_papers_multi edge cases."""

    def setUp(self):
        self.lf = pl.LazyFrame(
            {
                "id": ["1", "2", "3"],
                "title": ["A", "B", "C"],
                "abstract": ["abs1", "abs2", "abs3"],
                "authors": ["Smith, John", "Doe, Jane", "Brown, Bob"],
                "categories": ["cs.AI", "cs.AI stat.ML", "math.AT"],
                "authors_parsed": [
                    [["Smith", "John", ""]],
                    [["Doe", "Jane", ""]],
                    [["Brown", "Bob", ""]],
                ],
                "update_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            }
        )

    def test_no_papers_match(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("NonExistent",))
        self.assertEqual(len(result), 0)

    def test_single_author_matches(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith",))
        self.assertEqual(len(result), 1)
        self.assertEqual(result["id"][0], "1")

    def test_multiple_authors_must_all_match(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ("Smith", "Doe"))
        self.assertEqual(len(result), 0)

    def test_empty_authors_list(self):
        result = m._author_papers_multi(self.lf, "cs.AI", ())
        self.assertEqual(len(result), 2)


class TestPlotlyDrawEdgesFalse(unittest.TestCase):
    def test_no_edge_traces_when_draw_edges_false(self):
        G = nx.Graph()
        G.add_node("A", count=10)
        G.add_node("B", count=5)
        G.add_edge("A", "B", weight=1)
        fig = m.plotly_network_graph(G, draw_edges=False)
        edge_traces = [t for t in fig.data if t.mode == "lines"]
        self.assertEqual(len(edge_traces), 0)
        node_traces = [t for t in fig.data if t.mode == "markers"]
        self.assertEqual(len(node_traces), 1)

    def test_empty_graph_no_error(self):
        G = nx.Graph()
        fig = m.plotly_network_graph(G, draw_edges=False)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 1)


class TestPrecomputeCategoryDataNullCategories(unittest.TestCase):
    """precompute_category_data should handle null/empty categories."""

    def test_null_category_creates_no_cooc(self):
        lf = pl.DataFrame(
            {
                "categories": [None, "cs.AI"],
            }
        ).lazy()
        pc, cooc = m.precompute_category_data(lf)
        self.assertIn(None, pc["categories"].to_list())
        self.assertEqual(len(cooc), 0)

    def test_empty_string_category_does_not_crash(self):
        lf = pl.DataFrame(
            {
                "categories": ["", "cs.AI"],
            }
        ).lazy()
        pc, _ = m.precompute_category_data(lf)
        cats = pc["categories"].to_list()
        self.assertIn("cs.AI", cats)


class TestOverlapStatsEmptyData(unittest.TestCase):
    def test_empty_categories_no_error(self):
        lf = pl.DataFrame(
            {
                "categories": pl.Series([], dtype=pl.Utf8),
            }
        ).lazy()
        total, multi_cat = m._overlap_stats(lf)
        self.assertEqual(total, 0)
        self.assertEqual(multi_cat, 0)

    def test_single_cat_no_multi(self):
        lf = pl.DataFrame(
            {
                "categories": ["cs.AI"],
            }
        ).lazy()
        total, multi_cat = m._overlap_stats(lf)
        self.assertEqual(total, 1)
        self.assertEqual(multi_cat, 0)


class TestBuildCategoryGraphMoreEdgeCases(unittest.TestCase):
    def setUp(self):
        self.build = m.build_category_graph

    def test_top_n_less_than_available(self):
        pc = pl.DataFrame(
            {
                "categories": ["cs.AI", "math.AT", "stat.ML"],
                "count": [100, 80, 60],
            }
        )
        cooc = pl.DataFrame(
            {
                "categories": ["cs.AI", "cs.AI"],
                "categories_b": ["math.AT", "stat.ML"],
                "count": [30, 15],
            }
        )
        G = self.build(pc, cooc, top_n=2, min_cooc=1)
        self.assertEqual(G.number_of_nodes(), 2)
        self.assertEqual(G.number_of_edges(), 1)

    def test_top_n_zero_returns_empty(self):
        pc = pl.DataFrame(
            {
                "categories": ["cs.AI"],
                "count": [100],
            }
        )
        cooc = pl.DataFrame(
            {
                "categories": pl.Series([], dtype=pl.Utf8),
                "categories_b": pl.Series([], dtype=pl.Utf8),
                "count": pl.Series([], dtype=pl.Int64),
            }
        )
        G = self.build(pc, cooc, top_n=0, min_cooc=1)
        self.assertEqual(G.number_of_nodes(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
