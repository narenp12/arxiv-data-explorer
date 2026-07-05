"""Build-time Bayesian Poisson VAR inference for arXiv category dynamics.

Reads:  static/data/timeseries/*.json
        static/data/category_graph.json
Writes: static/data/causal_edges.json
        static/data/category_dynamics.json
"""

import json
import os
import warnings
from pathlib import Path

import numpy as np
import jax.numpy as jnp
from jax import random
import numpyro
import numpyro.distributions as dist
from numpyro.infer import MCMC, NUTS, Predictive

DATA_DIR = Path(__file__).resolve().parent.parent / "static" / "data"
RNG_KEY = random.PRNGKey(0)
WARMUP = 1000
SAMPLES = 500
CHAINS = 2


def load_timeseries(data_dir: Path) -> tuple[dict[str, list[float]], list[str], int]:
    """Load monthly category paper counts into a dict mapping category -> list."""
    ts_dir = data_dir / "timeseries"
    files = sorted(ts_dir.glob("*.json"))
    months = len(files)
    series: dict[str, list[float]] = {}
    for f in files:
        with open(f) as fh:
            month_data = json.load(fh)
        for cat, count in month_data.items():
            if cat not in series:
                series[cat] = [0.0] * months
            idx = files.index(f)
            series[cat][idx] = float(count)
    cats = sorted(series.keys())
    return series, cats, months


def load_graph(data_dir: Path, cats: list[str]) -> list[list[int]]:
    """Build neighbor list from category graph adjacency."""
    with open(data_dir / "category_graph.json") as f:
        graph = json.load(f)
    edges = graph.get("edges", graph.get("links", []))
    cat_index = {c: i for i, c in enumerate(cats)}
    adj: list[set[int]] = [set() for _ in cats]
    for e in edges:
        s = e.get("source", e.get("from"))
        t = e.get("target", e.get("to"))
        if s in cat_index and t in cat_index:
            adj[cat_index[s]].add(cat_index[t])
            adj[cat_index[t]].add(cat_index[s])
    return [sorted(nb) for nb in adj]


def poisson_var_model(
    y: jnp.ndarray,
    neighbor_lags: jnp.ndarray,
    n_neighbors: int,
    n_time: int,
):
    """Poisson VAR(1) with Normal priors on graph-neighbor coefficients."""
    alpha = numpyro.sample("alpha", dist.Normal(0, 5))
    trend = numpyro.sample("trend", dist.Normal(0, 1))
    month_effect = numpyro.sample("month_effect", dist.Normal(0, jnp.ones(11)))

    theta = numpyro.sample("theta", dist.Normal(0, 0.5 * jnp.ones(n_neighbors)))

    month_dummies = jnp.eye(11)
    se = jnp.concatenate([jnp.zeros((1, 11)), month_dummies])

    log_rate = alpha + trend * jnp.arange(n_time) + se @ month_effect
    neighbor_influence = theta @ neighbor_lags
    log_rate = log_rate + neighbor_influence

    numpyro.sample("obs", dist.Poisson(jnp.exp(log_rate)), obs=y)


def fit_category(
    cat: str,
    y: np.ndarray,
    neighbors: list[int],
    all_series: dict[str, list[float]],
) -> dict:
    """Fit Poisson VAR for one category, return edge posteriors."""
    n_time = len(y)
    n_neighbors = len(neighbors)
    cat_keys = list(all_series.keys())

    if n_neighbors == 0:
        return {
            "id": cat,
            "trend": 0.0,
            "trend_ci": [0.0, 0.0],
            "edges": [],
        }

    cat_keys = list(all_series.keys())
    neighbor_lags = jnp.array([
        jnp.log(1 + jnp.roll(jnp.array(all_series[cat_keys[nb]]), 1))
        for nb in neighbors
    ])
    neighbor_lags = neighbor_lags.at[:, 0].set(0.0)

    kernel = NUTS(poisson_var_model)
    mcmc = MCMC(kernel, num_warmup=WARMUP, num_samples=SAMPLES, num_chains=CHAINS)
    mcmc.run(
        RNG_KEY,
        y=jnp.array(y),
        neighbor_lags=neighbor_lags,
        n_neighbors=n_neighbors,
        n_time=n_time,
    )

    samples = mcmc.get_samples()
    theta = np.array(samples["theta"])
    theta_mean = theta.mean(axis=0)
    theta_ci = np.percentile(theta, [2.5, 97.5], axis=0)
    trend_mean = float(np.array(samples["trend"]).mean())
    trend_ci = np.percentile(np.array(samples["trend"]), [2.5, 97.5]).tolist()

    edges = []
    for k, nb_idx in enumerate(neighbors):
        prob = max(0.0, min(1.0, (theta[:, k] > 0).mean()))  # P(positive effect)
        edges.append({
            "source": cat_keys[nb_idx],
            "target": cat,
            "weight": round(float(theta_mean[k]), 5),
            "ci_lower": round(float(theta_ci[0, k]), 5),
            "ci_upper": round(float(theta_ci[1, k]), 5),
            "prob": round(prob, 3),
        })

    return {
        "id": cat,
        "trend": trend_mean,
        "trend_ci": [round(float(trend_ci[0]), 5), round(float(trend_ci[1]), 5)],
        "edges": edges,
    }


def main():
    series, cats, n_months = load_timeseries(DATA_DIR)
    neighbors = load_graph(DATA_DIR, cats)

    results = []
    for i, cat in enumerate(cats):
        y = np.array(series[cat])
        print(f"[{i+1}/{len(cats)}] {cat}")
        result = fit_category(cat, y, neighbors[i], series)
        results.append(result)

    all_edges = []
    for r in results:
        all_edges.extend(r["edges"])

    cat_summaries = [
        {
            "id": r["id"],
            "trend": r["trend"],
            "trend_ci": r["trend_ci"],
        }
        for r in results
    ]

    with open(DATA_DIR / "causal_edges.json", "w") as f:
        json.dump({"edges": all_edges, "categories": cat_summaries}, f, indent=2)

    with open(DATA_DIR / "category_dynamics.json", "w") as f:
        dynamics = {}
        for cat in cats:
            y = series[cat]
            dynamics[cat] = {"months": list(range(n_months)), "observed": y}
        json.dump(dynamics, f, indent=2)

    print(f"Done. {len(all_edges)} edges, {len(cat_summaries)} categories")


if __name__ == "__main__":
    main()
