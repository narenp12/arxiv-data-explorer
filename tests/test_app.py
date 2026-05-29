import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shared_mock import install_streamlit_mock
install_streamlit_mock()

SRC = os.path.join(HERE, "..", "arxiv_explorer")
sys.path.insert(0, SRC)

import unittest
import polars as pl
import numpy as np
import plotly.graph_objects as go
import app


class TestDashboardKpis(unittest.TestCase):
    def test_returns_three_values(self):
        lf = pl.DataFrame({
            "categories": ["cs.AI stat.ML", "math.AT", "cs.AI"],
            "authors_parsed": [
                [["Smith", "John", ""], ["Doe", "Jane", ""]],
                [["Wilson", "Bob", ""]],
                [["Smith", "John", ""]],
            ],
        }).lazy()
        total, n_cats, n_authors = app._dashboard_kpis(lf)
        self.assertEqual(total, 3)
        self.assertEqual(n_cats, 3)
        self.assertEqual(n_authors, 3)

    def test_empty_data(self):
        lf = pl.DataFrame({
            "categories": pl.Series([], dtype=pl.Utf8),
            "authors_parsed": pl.Series([], dtype=pl.List(pl.List(pl.Utf8))),
        }).lazy()
        total, n_cats, n_authors = app._dashboard_kpis(lf)
        self.assertEqual(total, 0)
        self.assertEqual(n_cats, 0)
        self.assertEqual(n_authors, 0)

    def test_duplicate_authors_across_papers(self):
        lf = pl.DataFrame({
            "categories": ["cs.AI", "cs.AI"],
            "authors_parsed": [
                [["Smith", "John", ""]],
                [["Smith", "John", ""]],
            ],
        }).lazy()
        _, _, n_authors = app._dashboard_kpis(lf)
        self.assertEqual(n_authors, 1)

    def test_duplicate_categories(self):
        lf = pl.DataFrame({
            "categories": ["cs.AI", "cs.AI"],
            "authors_parsed": [
                [["Smith", "John", ""]],
                [["Doe", "Jane", ""]],
            ],
        }).lazy()
        _, n_cats, _ = app._dashboard_kpis(lf)
        self.assertEqual(n_cats, 1)

    def test_multi_category_paper(self):
        lf = pl.DataFrame({
            "categories": ["cs.AI stat.ML math.AT"],
            "authors_parsed": [
                [["Smith", "John", ""]],
            ],
        }).lazy()
        _, n_cats, _ = app._dashboard_kpis(lf)
        self.assertEqual(n_cats, 3)


class TestSearchCategories(unittest.TestCase):
    def test_returns_sorted_unique(self):
        lf = pl.DataFrame({
            "categories": ["cs.AI", "math.AT", "cs.AI", "stat.ML"],
        }).lazy()
        result = app._search_categories(lf)
        self.assertEqual(result, ["cs.AI", "math.AT", "stat.ML"])

    def test_handles_multi_category_strings(self):
        lf = pl.DataFrame({
            "categories": ["cs.AI stat.ML", "math.AT"],
        }).lazy()
        result = app._search_categories(lf)
        self.assertEqual(result, ["cs.AI", "math.AT", "stat.ML"])

    def test_empty_data(self):
        lf = pl.DataFrame({
            "categories": pl.Series([], dtype=pl.Utf8),
        }).lazy()
        result = app._search_categories(lf)
        self.assertEqual(result, [])


class TestSearchYearRange(unittest.TestCase):
    def test_returns_min_max(self):
        lf = pl.DataFrame({
            "update_date": ["2020-01-01", "2023-06-15", "2021-12-31"],
        }).lazy()
        ymin, ymax = app._search_year_range(lf)
        self.assertEqual(ymin, 2020)
        self.assertEqual(ymax, 2023)

    def test_single_year(self):
        lf = pl.DataFrame({
            "update_date": ["2022-03-01", "2022-03-01"],
        }).lazy()
        ymin, ymax = app._search_year_range(lf)
        self.assertEqual(ymin, 2022)
        self.assertEqual(ymax, 2022)

    def test_empty_data_raises(self):
        lf = pl.DataFrame({
            "update_date": pl.Series([], dtype=pl.Utf8),
        }).lazy()
        with self.assertRaises(Exception):
            app._search_year_range(lf)


class TestAuthorDistribution(unittest.TestCase):
    def test_returns_binned_counts(self):
        lf = pl.DataFrame({
            "authors_parsed": [
                [["Smith", "John", ""]],
                [["Smith", "John", ""], ["Doe", "Jane", ""]],
                [],
            ],
        }).lazy()
        result = app._author_distribution(lf)
        self.assertIn("n_auth_binned", result.columns)
        self.assertIn("count", result.columns)
        self.assertEqual(result["n_auth_binned"].to_list(), [0, 1, 2])
        self.assertEqual(result["count"].to_list(), [1, 1, 1])

    def test_empty_data(self):
        lf = pl.DataFrame({
            "authors_parsed": pl.Series([], dtype=pl.List(pl.List(pl.Utf8))),
        }).lazy()
        result = app._author_distribution(lf)
        self.assertEqual(len(result), 0)

    def test_caps_at_51(self):
        lf = pl.DataFrame({
            "authors_parsed": [
                [["A", "B", ""]] * 100,
            ],
        }).lazy()
        result = app._author_distribution(lf)
        self.assertIn(51, result["n_auth_binned"].to_list())


class TestSearchPapers(unittest.TestCase):
    def test_no_filters_returns_all(self):
        lf = pl.DataFrame({
            "id": ["1", "2"],
            "title": ["Quantum gravity", "Machine learning"],
            "abstract": ["abstract 1", "abstract 2"],
            "categories": ["cs.AI", "stat.ML"],
            "update_date": ["2020-01-01", "2021-01-01"],
            "authors": ["John Smith", "Jane Doe"],
        }).lazy()
        result = app.search_papers(lf, "", "All", None, "")
        self.assertEqual(len(result), 2)

    def test_query_filter_title(self):
        lf = pl.DataFrame({
            "id": ["1", "2"],
            "title": ["Quantum gravity", "Machine learning"],
            "abstract": ["foo", "bar"],
            "categories": ["cs.AI", "stat.ML"],
            "update_date": ["2020-01-01", "2021-01-01"],
            "authors": ["John Smith", "Jane Doe"],
        }).lazy()
        result = app.search_papers(lf, "Quantum", "All", None, "")
        self.assertEqual(len(result), 1)
        self.assertEqual(result["id"][0], "1")

    def test_query_filter_abstract(self):
        lf = pl.DataFrame({
            "id": ["1", "2"],
            "title": ["Paper 1", "Paper 2"],
            "abstract": ["about quantum gravity", "about machine learning"],
            "categories": ["cs.AI", "stat.ML"],
            "update_date": ["2020-01-01", "2021-01-01"],
            "authors": ["John Smith", "Jane Doe"],
        }).lazy()
        result = app.search_papers(lf, "quantum", "All", None, "")
        self.assertEqual(len(result), 1)

    def test_category_filter(self):
        lf = pl.DataFrame({
            "id": ["1", "2", "3"],
            "title": ["a", "b", "c"],
            "abstract": ["x", "y", "z"],
            "categories": ["cs.AI", "stat.ML", "cs.AI"],
            "update_date": ["2020-01-01", "2021-01-01", "2022-01-01"],
            "authors": ["A", "B", "C"],
        }).lazy()
        result = app.search_papers(lf, "", "cs.AI", None, "")
        self.assertEqual(len(result), 2)

    def test_year_range_filter(self):
        lf = pl.DataFrame({
            "id": ["1", "2", "3"],
            "title": ["a", "b", "c"],
            "abstract": ["x", "y", "z"],
            "categories": ["cs.AI", "stat.ML", "math.AT"],
            "update_date": ["2020-01-01", "2021-01-01", "2022-01-01"],
            "authors": ["A", "B", "C"],
        }).lazy()
        result = app.search_papers(lf, "", "All", (2021, 2022), "")
        self.assertEqual(len(result), 2)

    def test_author_filter(self):
        lf = pl.DataFrame({
            "id": ["1", "2"],
            "title": ["a", "b"],
            "abstract": ["x", "y"],
            "categories": ["cs.AI", "stat.ML"],
            "update_date": ["2020-01-01", "2021-01-01"],
            "authors": ["John Smith", "Jane Doe"],
        }).lazy()
        result = app.search_papers(lf, "", "All", None, "Smith")
        self.assertEqual(len(result), 1)

    def test_combined_filters(self):
        lf = pl.DataFrame({
            "id": ["1", "2", "3"],
            "title": ["Quantum ML", "Classical ML", "Quantum physics"],
            "abstract": ["x", "y", "z"],
            "categories": ["cs.AI", "stat.ML", "physics.gen-ph"],
            "update_date": ["2020-01-01", "2021-01-01", "2022-01-01"],
            "authors": ["Smith, John", "Doe, Jane", "Brown, Bob"],
        }).lazy()
        result = app.search_papers(lf, "Quantum", "cs.AI", (2020, 2021), "Smith")
        self.assertEqual(len(result), 1)

    def test_empty_result(self):
        lf = pl.DataFrame({
            "id": ["1"],
            "title": ["Paper"],
            "abstract": ["abstract"],
            "categories": ["cs.AI"],
            "update_date": ["2020-01-01"],
            "authors": ["Author"],
        }).lazy()
        result = app.search_papers(lf, "NonexistentTermXYZ", "All", None, "")
        self.assertEqual(len(result), 0)


class TestGetLicenseCounts(unittest.TestCase):
    def test_basic_counts(self):
        lf = pl.DataFrame({
            "license": [
                "http://arxiv.org/licenses/nonexclusive-distrib/1.0/",
                "http://creativecommons.org/licenses/by/4.0/",
                "http://creativecommons.org/licenses/by-nc-nd/4.0/",
                None,
                "http://arxiv.org/licenses/nonexclusive-distrib/1.0/",
            ],
        }).lazy()
        result = app.get_license_counts(lf)
        self.assertIn("license_short", result.columns)
        self.assertIn("count", result.columns)
        counts = dict(zip(result["license_short"], result["count"]))
        self.assertEqual(counts.get("arXiv nonexclusive"), 2)
        self.assertEqual(counts.get("CC BY 4.0"), 1)
        self.assertEqual(counts.get("CC BY-NC-ND 4.0"), 1)
        self.assertEqual(counts.get("Missing"), 1)

    def test_empty_data(self):
        lf = pl.DataFrame({
            "license": pl.Series([], dtype=pl.Utf8),
        }).lazy()
        result = app.get_license_counts(lf)
        self.assertEqual(len(result), 0)

    def test_unknown_license(self):
        lf = pl.DataFrame({
            "license": ["some-unknown-license"],
        }).lazy()
        result = app.get_license_counts(lf)
        counts = dict(zip(result["license_short"], result["count"]))
        self.assertEqual(counts.get("Other"), 1)

    def test_cc_by_nc_sa_4_0(self):
        lf = pl.DataFrame({
            "license": ["http://creativecommons.org/licenses/by-nc-sa/4.0/"],
        }).lazy()
        result = app.get_license_counts(lf)
        counts = dict(zip(result["license_short"], result["count"]))
        self.assertEqual(counts.get("CC BY-NC-SA 4.0"), 1)

    def test_cc_by_sa_4_0(self):
        lf = pl.DataFrame({
            "license": ["http://creativecommons.org/licenses/by-sa/4.0/"],
        }).lazy()
        result = app.get_license_counts(lf)
        counts = dict(zip(result["license_short"], result["count"]))
        self.assertEqual(counts.get("CC BY-SA 4.0"), 1)

    def test_cc0_1_0(self):
        lf = pl.DataFrame({
            "license": ["http://creativecommons.org/publicdomain/zero/1.0/"],
        }).lazy()
        result = app.get_license_counts(lf)
        counts = dict(zip(result["license_short"], result["count"]))
        self.assertEqual(counts.get("CC0 1.0"), 1)
class TestGetNullCounts(unittest.TestCase):
    def test_all_present(self):
        lf = pl.DataFrame({
            "title": ["a", "b"],
            "abstract": ["x", "y"],
        }).lazy()
        result = app.get_null_counts(lf)
        self.assertTrue((result["filled_pct"] == 1.0).all())

    def test_some_null(self):
        lf = pl.DataFrame({
            "title": ["a", None],
            "abstract": ["x", "y"],
        }).lazy()
        result = app.get_null_counts(lf)
        counts = dict(zip(result["column"], result["null_count"]))
        self.assertEqual(counts.get("title"), 1)
        self.assertEqual(counts.get("abstract"), 0)

    def test_empty_data(self):
        lf = pl.DataFrame({
            "title": pl.Series([], dtype=pl.Utf8),
            "abstract": pl.Series([], dtype=pl.Utf8),
        }).lazy()
        result = app.get_null_counts(lf)
        self.assertEqual(len(result), 2)


class TestCatCountsHistogram(unittest.TestCase):
    def test_returns_list(self):
        lf = pl.DataFrame({
            "categories": ["cs.AI", "cs.AI stat.ML", "math.AT"],
        }).lazy()
        result = app._cat_counts_histogram(lf)
        self.assertEqual(result, [1, 2, 1])

    def test_empty_data(self):
        lf = pl.DataFrame({
            "categories": pl.Series([], dtype=pl.Utf8),
        }).lazy()
        result = app._cat_counts_histogram(lf)
        self.assertEqual(result, [])


class TestCooccurrenceMatrix(unittest.TestCase):
    def test_returns_top_categories_and_matrix(self):
        lf = pl.DataFrame({
            "categories": ["cs.AI stat.ML", "cs.AI", "stat.ML math.AT"],
        }).lazy()
        cats, matrix = app._cooccurrence_matrix(lf, ["cs.AI", "stat.ML"])
        self.assertEqual(cats, ["cs.AI", "stat.ML"])
        self.assertEqual(matrix.shape, (2, 2))
        self.assertTrue(np.isnan(matrix[0, 0]))
        self.assertTrue(np.isnan(matrix[1, 1]))


class TestBrowsePapers(unittest.TestCase):
    def test_returns_matching_papers(self):
        lf = pl.DataFrame({
            "id": ["1", "2", "3"],
            "title": ["Paper A", "Paper B", "Paper C"],
            "categories": ["cs.AI", "stat.ML", "cs.AI"],
        }).lazy()
        result = app._browse_papers(lf, "cs.AI")
        self.assertEqual(len(result), 2)
        self.assertEqual(result["id"].to_list(), ["1", "3"])

    def test_empty_result(self):
        lf = pl.DataFrame({
            "id": ["1"],
            "title": ["Paper"],
            "categories": ["cs.AI"],
        }).lazy()
        result = app._browse_papers(lf, "math.AT")
        self.assertEqual(len(result), 0)


class TestLoadDateDf(unittest.TestCase):
    def test_returns_date_year_month(self):
        lf = pl.DataFrame({
            "update_date": ["2020-01-05", "2021-06-15"],
        }).lazy()
        result = app.load_date_df(lf)
        self.assertIn("date", result.columns)
        self.assertIn("year", result.columns)
        self.assertIn("month", result.columns)
        self.assertEqual(result["year"].to_list(), [2020, 2021])
        self.assertEqual(result["month"].to_list(), [1, 6])

    def test_handles_null_update_date(self):
        lf = pl.DataFrame({
            "update_date": [None, "2020-01-05"],
        }).lazy()
        result = app.load_date_df(lf)
        self.assertTrue(result["date"].is_null().sum() == 1)

    def test_empty_data(self):
        lf = pl.DataFrame({
            "update_date": pl.Series([], dtype=pl.Utf8),
        }).lazy()
        result = app.load_date_df(lf)
        self.assertEqual(len(result), 0)


class TestGetTopCategories(unittest.TestCase):
    def test_returns_top_n(self):
        lf = pl.DataFrame({
            "categories": ["cs.AI", "cs.AI", "math.AT", "stat.ML"],
        }).lazy()
        result = app.get_top_categories(lf, n=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result["categories"][0], "cs.AI")

    def test_returns_label_column(self):
        lf = pl.DataFrame({
            "categories": ["cs.AI"],
        }).lazy()
        result = app.get_top_categories(lf, n=5)
        self.assertIn("label", result.columns)

    def test_empty_data(self):
        lf = pl.DataFrame({
            "categories": pl.Series([], dtype=pl.Utf8),
        }).lazy()
        result = app.get_top_categories(lf, n=10)
        self.assertEqual(len(result), 0)

    def test_returns_sorted_by_count_desc(self):
        lf = pl.DataFrame({
            "categories": ["math.AT", "cs.AI", "cs.AI", "stat.ML", "stat.ML", "stat.ML"],
        }).lazy()
        result = app.get_top_categories(lf, n=10)
        self.assertEqual(result["categories"][0], "stat.ML")
        self.assertEqual(result["count"][0], 3)


class TestGetYearCounts(unittest.TestCase):
    def test_returns_year_and_count(self):
        df = pl.DataFrame({
            "year": [2020, 2020, 2021],
            "date": ["2020-01-01", "2020-06-01", "2021-01-01"],
            "month": [1, 6, 1],
        })
        result = app.get_year_counts(df)
        self.assertIn("year", result.columns)
        self.assertIn("count", result.columns)

    def test_groups_correctly(self):
        df = pl.DataFrame({
            "year": [2020, 2020, 2021],
            "date": ["2020-01-01", "2020-06-01", "2021-01-01"],
            "month": [1, 6, 1],
        })
        result = app.get_year_counts(df)
        counts = dict(zip(result["year"], result["count"]))
        self.assertEqual(counts[2020], 2)
        self.assertEqual(counts[2021], 1)

    def test_empty_data(self):
        df = pl.DataFrame({
            "year": pl.Series([], dtype=pl.Int32),
            "date": pl.Series([], dtype=pl.Utf8),
            "month": pl.Series([], dtype=pl.Int32),
        })
        result = app.get_year_counts(df)
        self.assertEqual(len(result), 0)


class TestGetMonthCounts(unittest.TestCase):
    def test_returns_month_and_count(self):
        df = pl.DataFrame({
            "month": [1, 1, 2],
            "year": [2020, 2020, 2020],
            "date": ["2020-01-01", "2020-01-02", "2020-02-01"],
        })
        result = app.get_month_counts(df)
        self.assertIn("month", result.columns)
        self.assertIn("count", result.columns)

    def test_groups_correctly(self):
        df = pl.DataFrame({
            "month": [1, 1, 2],
            "year": [2020, 2020, 2020],
            "date": ["2020-01-01", "2020-01-02", "2020-02-01"],
        })
        result = app.get_month_counts(df)
        counts = dict(zip(result["month"], result["count"]))
        self.assertEqual(counts[1], 2)
        self.assertEqual(counts[2], 1)

    def test_empty_data(self):
        df = pl.DataFrame({
            "month": pl.Series([], dtype=pl.Int32),
            "year": pl.Series([], dtype=pl.Int32),
            "date": pl.Series([], dtype=pl.Utf8),
        })
        result = app.get_month_counts(df)
        self.assertEqual(len(result), 0)


class TestTop50Authors(unittest.TestCase):
    def test_returns_last_name_and_count(self):
        lf = pl.DataFrame({
            "authors_parsed": [
                [["Smith", "John", ""]],
                [["Smith", "John", ""], ["Doe", "Jane", ""]],
                [["Wilson", "Bob", ""]],
            ],
        }).lazy()
        result = app._top50_authors(lf)
        self.assertIn("authors_parsed", result.columns)
        self.assertIn("count", result.columns)

    def test_sorted_by_count_desc(self):
        lf = pl.DataFrame({
            "authors_parsed": [
                [["A", "X", ""]] * 5,
                [["B", "Y", ""]] * 3,
                [["C", "Z", ""]] * 1,
            ],
        }).lazy()
        result = app._top50_authors(lf)
        self.assertEqual(result["authors_parsed"][0], "A")
        self.assertEqual(result["count"][0], 5)

    def test_capped_at_50(self):
        authors = [[[str(i), "X", ""]] for i in range(100)]
        lf = pl.DataFrame({
            "authors_parsed": authors,
        }).lazy()
        result = app._top50_authors(lf)
        self.assertEqual(len(result), 50)

    def test_empty_data(self):
        lf = pl.DataFrame({
            "authors_parsed": pl.Series([], dtype=pl.List(pl.List(pl.Utf8))),
        }).lazy()
        result = app._top50_authors(lf)
        self.assertEqual(len(result), 0)


class TestVersionStats(unittest.TestCase):
    def test_returns_n_versions(self):
        lf = pl.DataFrame({
            "versions": [["v1", "v2"], ["v1"], None],
        }).lazy()
        result = app._version_stats(lf)
        self.assertIn("n_versions", result.columns)
        self.assertEqual(result["n_versions"].to_list(), [2, 1, None])

    def test_empty_data(self):
        lf = pl.DataFrame({
            "versions": pl.Series([], dtype=pl.List(pl.Utf8)),
        }).lazy()
        result = app._version_stats(lf)
        self.assertEqual(len(result), 0)


class TestTextStats(unittest.TestCase):
    def test_returns_title_and_abstract_len(self):
        lf = pl.DataFrame({
            "title": ["Short", "A longer title here"],
            "abstract": ["Abs one", "A much longer abstract that goes on for testing"],
        }).lazy()
        result = app._text_stats(lf)
        self.assertIn("title_len", result.columns)
        self.assertIn("abstract_len", result.columns)
        self.assertEqual(result["title_len"].to_list(), [5, 19])
        self.assertEqual(result["abstract_len"].to_list(), [7, 47])

    def test_empty_data(self):
        lf = pl.DataFrame({
            "title": pl.Series([], dtype=pl.Utf8),
            "abstract": pl.Series([], dtype=pl.Utf8),
        }).lazy()
        result = app._text_stats(lf)
        self.assertEqual(len(result), 0)


class TestCommentsStats(unittest.TestCase):
    def test_returns_comments_metrics(self):
        lf = pl.DataFrame({
            "comments": ["6 pages, 3 figures", "No comments", "10 references"],
        }).lazy()
        result = app._comments_stats(lf)
        self.assertIn("comments_len", result.columns)
        self.assertIn("has_pages", result.columns)
        self.assertIn("has_figures", result.columns)
        self.assertIn("has_refs", result.columns)

    def test_detects_pages(self):
        lf = pl.DataFrame({
            "comments": ["6 pages", "no count"],
        }).lazy()
        result = app._comments_stats(lf)
        self.assertEqual(result["has_pages"].to_list(), [True, False])

    def test_detects_figures(self):
        lf = pl.DataFrame({
            "comments": ["3 figures", "none"],
        }).lazy()
        result = app._comments_stats(lf)
        self.assertEqual(result["has_figures"].to_list(), [True, False])

    def test_detects_references(self):
        lf = pl.DataFrame({
            "comments": ["25 references", "none"],
        }).lazy()
        result = app._comments_stats(lf)
        self.assertEqual(result["has_refs"].to_list(), [True, False])

    def test_empty_data(self):
        lf = pl.DataFrame({
            "comments": pl.Series([], dtype=pl.Utf8),
        }).lazy()
        result = app._comments_stats(lf)
        self.assertEqual(len(result), 0)


class TestYearBarChart(unittest.TestCase):
    def setUp(self):
        app.st.plotly_chart.reset_mock()
        self.df = pl.DataFrame({
            "year": [2020, 2021, 2022],
            "count": [100, 150, 200],
        })

    def test_calls_plotly_chart(self):
        app._year_bar_chart(self.df)
        app.st.plotly_chart.assert_called_once()

    def test_passes_figure(self):
        app._year_bar_chart(self.df)
        fig = app.st.plotly_chart.call_args[0][0]
        self.assertIsInstance(fig, go.Figure)


class TestMonthBarChart(unittest.TestCase):
    def setUp(self):
        app.st.plotly_chart.reset_mock()
        self.df = pl.DataFrame({
            "month": [1, 2, 3],
            "count": [50, 75, 100],
        })

    def test_calls_plotly_chart(self):
        app._month_bar_chart(self.df, "Test Title")
        app.st.plotly_chart.assert_called_once()

    def test_passes_figure(self):
        app._month_bar_chart(self.df, "Test Title")
        fig = app.st.plotly_chart.call_args[0][0]
        self.assertIsInstance(fig, go.Figure)

    def test_month_names_applied(self):
        app._month_bar_chart(self.df, "Test Title")
        fig = app.st.plotly_chart.call_args[0][0]
        x_vals = fig.data[0]["x"]
        self.assertEqual(list(x_vals), ["Jan", "Feb", "Mar"])
