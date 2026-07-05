# Causal Trends — Bayesian Poisson VAR with Graph Regularization

## 1. Purpose

Add a new section to the arXiv Data Explorer that infers a **causal graph over arXiv categories** using Bayesian time series modeling. Each directed edge represents "category *j*'s past paper count predicts category *i*'s current paper count" (Granger causality), with full posterior uncertainty.

## 2. Data

| Source | Shape | Notes |
|---|---|---|
| `static/data/timeseries/*.json` | 169 categories × 227 months (2007-05 → 2026-03) | Monthly paper counts per category |
| `static/data/category_graph.json` | 169 nodes, weighted edges | Co-occurrence prior for the VAR |
| `static/data/category_hierarchy.json` | domain → subcategory | Domain labels for filtering |

Total: 5.1M paper-count events across all categories and months.

## 3. Model

For each category *i* independently:

```
y_{i,t}  ~  Poisson(λ_{i,t})

log(λ_{i,t})  =  α_i  +  β_i · t  +  Σ_m γ_m · δ_{t,m}  +  Σ_{j∈N(i)} a_{i,j} · log(y_{j,t-1} + 1)
```

| Parameter | Count | Prior | Role |
|---|---|---|---|
| `α_i` | 169 | Normal(0, 5) | Category base rate |
| `β_i` | 169 | Normal(0, 1) | Long-term trend |
| `γ_m` | 11 | Normal(0, 1) | Seasonality (month-of-year) |
| `a_{i,j}` | ~30/category | Spike-and-slab | Excitation / Granger-causal weight |

**Regularization:** The set `N(i)` is the graph neighbors of *i* in the co-occurrence graph (5–30 neighbors per category). Each `a_{i,j}` uses a spike-and-slab prior:

```
z_{i,j}  ~  Bernoulli(p)
a_{i,j} | z_{i,j}=1  ~  Normal(0, 0.5)
a_{i,j} | z_{i,j}=0  =  0
```

where `p` is a shared sparsity hyperparameter (~0.3, weakly regularized Beta prior).

**Inference:** NumPyro, HMC (NUTS), 1000 warmup + 500 samples, 2 chains. The 169 models are independent per-category so they run in parallel.

## 4. Output

Three JSON files, written to `static/data/` at build time:

### `causal_edges.json`

```json
{
  "edges": [
    {"source": "cs.LG", "target": "cs.AI", "weight": 0.042,
     "ci_lower": 0.012, "ci_upper": 0.071, "prob": 0.89}
  ],
  "categories": [
    {"id": "cs.LG", "trend": 0.031,
     "trend_ci": [0.025, 0.037], "base_rate": -2.1}
  ]
}
```

### `category_dynamics.json`

Fitted values + decomposition for each category-month, used for the trajectory charts.

### `model_summary.json`

Method description, neg-log-likelihood, model comparison metrics, runtime.

## 5. Frontend

### Route structure

| Route | Type | Description |
|---|---|---|
| `/trends` | CSR (`prerender = false`) | Interactive causal graph + dashboard |
| `/trends/[id]` | CSR | Category detail: trajectory + influences |
| `/takeoffs` | CSR | Ranked categories by growth/decline, filterable |

### `/trends` — Causal graph view

- D3 force-directed layout (reusing patterns from CategoryGraph.svelte)
- Nodes: arXiv categories, sized by paper count, colored by growth trend (green = growing, red = declining)
- Directed edges: causal influence, stroke width = posterior mean, opacity = posterior probability, color = positive (blue) / negative (red)
- Hover: tooltip showing `source → target: weight [ci_lower, ci_upper], P(edge) = prob`
- Click node: navigate to `/trends/[id]`
- Legend / key panel in corner
- Filter by domain dropdown (CS, Math, Physics, etc.)

### `/trends/[id]` — Category detail

- Top panel: line chart showing observed counts + posterior fitted values + 50% credible interval ribbon
- Middle panel: stacked area chart of decomposition — baseline + trend + seasonality + cross-category influence
- Bottom: "What drives this category?" — ranked list of incoming edges with weights + CIs
- Bottom: "What does this drive?" — ranked list of outgoing edges

### `/takeoffs` — Dashboard

- Table: category | growth rate | [CI] | domain | takeoff period | paper count
- Sortable columns
- Filter by domain (from hierarchy)
- Color bar: gradient from red (declining) → white (stable) → green (growing)

## 6. Build pipeline

```
npm run build
  → vite build (Svelte)
  → node scripts/postbuild.js
      → python3 scripts/poisson_var.py
      → (if missing deps, installs via pip)
```

The `postbuild.js` script runs the Python analysis and checks for its success. Dependencies must be pre-installed via `pip install -r scripts/requirements.txt` before the build.

## 7. Dependencies

Python (build-time only, not in production):
- `numpyro` — JAX-based Bayesian inference
- `jax` — autograd + JIT
- `numpy`, `scipy`

Installed via `pip install -r scripts/requirements.txt` before building.

## 8. State vs route handling

- `/trends` and `/trends/[id]` are CSR only (no prerender) because data loaded from static JSON is runtime (`onMount`/`$effect`)
- `/takeoffs` can be CSR for consistency

## 9. Outline of new/modified files

| File | Action |
|---|---|
| `scripts/postbuild.js` | Create — runs Python analysis after Vite build |
| `scripts/poisson_var.py` | Create — Bayesian Poisson VAR inference |
| `src/routes/trends/+page.svelte` | Create — causal graph view |
| `src/routes/trends/+layout.ts` | Create — `export const prerender = false` |
| `src/routes/trends/[id]/+page.svelte` | Create — category detail view |
| `src/routes/trends/[id]/+layout.ts` | Create — `export const prerender = false` |
| `src/routes/takeoffs/+page.svelte` | Create — growth dashboard |
| `src/routes/takeoffs/+layout.ts` | Create — `export const prerender = false` |
| `src/routes/+layout.svelte` | Modify — add "Trends" to nav sidebar |
| `package.json` | Modify — add postbuild script |

## 10. Future extensions

- **Dynamic causal graphs:** Fit on rolling 5-year windows to track how the causal structure evolves
- **Paper text fusion:** Incorporate topic model features as additional regressors
- **Multi-step forecasting:** Use the fitted VAR to predict arXiv growth 1-3 years out
- **Author migration:** Model author category-switching as a separate Markov process
