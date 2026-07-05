"""Deterministic trend + Granger-edge estimation for arXiv category dynamics.

Fast numpy replacement for the MCMC pipeline in poisson_var.py (which was
never run to completion — causal_edges.json shipped with zero edges and
category_dynamics.json was missing).

Reads:  static/data/timeseries/*.json
        static/data/category_graph.json
Writes: static/data/causal_edges.json
        static/data/category_dynamics.json

Method
------
Trends:  OLS on z = log1p(count) with intercept, linear month term and
         month-of-year dummies. `trend` is the monthly log-slope; the UI
         converts to annual % via expm1(12 * trend).
Edges:   per target category, ridge-regularized regression of z_t on
         [trend + seasonality + own lag + neighbor lags] restricted to
         category-graph neighbors. `prob` is the two-sided confidence
         that the coefficient's sign is real (always >= 0.5).
Backlog: months whose corpus-wide total exceeds 10x the median month are
         dropped (2007-05 contains the entire pre-2007 backlog).
"""

import json
import math
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "static" / "data"
MIN_ACTIVE_MONTHS = 24  # exclude long-dead legacy categories from the model
RIDGE_LAMBDA = 1.0      # penalty on lag coefficients only
EDGE_MIN_PROB = 0.90
EDGE_MIN_WEIGHT = 0.01
EDGE_MAX_PER_TARGET = 8


def norm_cdf(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.vectorize(math.erf)(x / math.sqrt(2.0)))


def load_timeseries() -> tuple[dict[str, np.ndarray], list[str], str]:
    files = sorted((DATA_DIR / "timeseries").glob("*.json"))
    raw = [json.loads(f.read_text()) for f in files]
    totals = np.array([sum(m.values()) for m in raw])
    keep = totals <= 10 * np.median(totals)
    dropped = [f.stem for f, k in zip(files, keep) if not k]
    if dropped:
        print(f"Dropped backlog months: {dropped}")
    files = [f for f, k in zip(files, keep) if k]
    raw = [m for m, k in zip(raw, keep) if k]

    cats = sorted({c for m in raw for c in m})
    series = {c: np.array([float(m.get(c, 0)) for m in raw]) for c in cats}
    start = files[0].stem  # e.g. "2007-06"
    return series, cats, start


def design_matrix(n: int) -> np.ndarray:
    """Intercept + linear trend + 11 month dummies."""
    t = np.arange(n, dtype=float)
    months = np.arange(n) % 12
    dummies = np.zeros((n, 11))
    for m in range(1, 12):
        dummies[months == m, m - 1] = 1.0
    return np.column_stack([np.ones(n), t, dummies])


def fit_trend(z: np.ndarray) -> tuple[float, tuple[float, float], float]:
    """OLS trend on log1p counts. Returns (slope, ci, zbar)."""
    n = len(z)
    X = design_matrix(n)
    beta, *_ = np.linalg.lstsq(X, z, rcond=None)
    resid = z - X @ beta
    dof = max(n - X.shape[1], 1)
    sigma2 = float(resid @ resid) / dof
    cov = sigma2 * np.linalg.inv(X.T @ X)
    se = math.sqrt(max(cov[1, 1], 1e-12))
    b = float(beta[1])
    return b, (b - 1.96 * se, b + 1.96 * se), float(z.mean())


def fit_edges(
    target: str,
    z_by_cat: dict[str, np.ndarray],
    neighbors: list[str],
) -> list[dict]:
    """Ridge regression of target on its own lag + neighbor lags."""
    if not neighbors:
        return []
    z = z_by_cat[target][1:]  # drop first obs (no lag available)
    n = len(z)
    base = design_matrix(n)
    own_lag = z_by_cat[target][:-1]
    lags = np.column_stack([own_lag] + [z_by_cat[nb][:-1] for nb in neighbors])
    X = np.column_stack([base, lags])
    k_base = base.shape[1]

    # ridge on lag coefficients only
    P = np.zeros(X.shape[1])
    P[k_base:] = RIDGE_LAMBDA
    XtX = X.T @ X + np.diag(P)
    XtX_inv = np.linalg.inv(XtX)
    beta = XtX_inv @ X.T @ z
    resid = z - X @ beta
    dof = max(n - X.shape[1], 1)
    sigma2 = float(resid @ resid) / dof
    cov = sigma2 * (XtX_inv @ (X.T @ X) @ XtX_inv)

    edges = []
    for j, nb in enumerate(neighbors):
        idx = k_base + 1 + j  # skip own lag
        w = float(beta[idx])
        se = math.sqrt(max(float(cov[idx, idx]), 1e-12))
        zscore = w / se
        conf = float(norm_cdf(np.array([abs(zscore)]))[0])  # P(sign is real)
        if conf < EDGE_MIN_PROB or abs(w) < EDGE_MIN_WEIGHT:
            continue
        edges.append({
            "source": nb,
            "target": target,
            "weight": round(w, 5),
            "ci_lower": round(w - 1.96 * se, 5),
            "ci_upper": round(w + 1.96 * se, 5),
            "prob": round(conf, 3),
        })
    edges.sort(key=lambda e: abs(e["weight"]) * e["prob"], reverse=True)
    return edges[:EDGE_MAX_PER_TARGET]


def load_neighbors(cats: list[str]) -> dict[str, list[str]]:
    graph = json.loads((DATA_DIR / "category_graph.json").read_text())
    edges = graph.get("edges", graph.get("links", []))
    cat_set = set(cats)
    adj: dict[str, set[str]] = {c: set() for c in cats}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in cat_set and t in cat_set and s != t:
            adj[s].add(t)
            adj[t].add(s)
    return {c: sorted(nb) for c, nb in adj.items()}


def main() -> None:
    series, cats, start = load_timeseries()
    active = [c for c in cats if int((series[c] > 0).sum()) >= MIN_ACTIVE_MONTHS]
    print(f"{len(cats)} categories, {len(active)} active, start {start}")

    z_by_cat = {c: np.log1p(series[c]) for c in active}
    neighbors = load_neighbors(active)

    categories = []
    all_edges = []
    n_months = len(next(iter(series.values())))
    tbar = float(np.arange(n_months, dtype=float).mean())
    for i, cat in enumerate(active):
        b, ci, zbar = fit_trend(z_by_cat[cat])
        categories.append({
            "id": cat,
            "trend": round(b, 5),
            "trend_ci": [round(ci[0], 5), round(ci[1], 5)],
            "anchor": [round(tbar, 2), round(zbar, 4)],
        })
        all_edges.extend(fit_edges(cat, z_by_cat, neighbors[cat]))
        if (i + 1) % 40 == 0:
            print(f"  fitted {i + 1}/{len(active)}")

    out = {
        "meta": {"start": start, "months": n_months, "units": "monthly log-slope"},
        "edges": all_edges,
        "categories": categories,
    }
    (DATA_DIR / "causal_edges.json").write_text(json.dumps(out))

    dynamics = {
        "meta": {"start": start, "months": n_months},
        "series": {c: [int(v) for v in series[c]] for c in cats},
    }
    (DATA_DIR / "category_dynamics.json").write_text(json.dumps(dynamics))

    kb = (DATA_DIR / "category_dynamics.json").stat().st_size / 1024
    print(f"Done. {len(all_edges)} edges, {len(categories)} categories, dynamics {kb:.0f}KB")


if __name__ == "__main__":
    main()
