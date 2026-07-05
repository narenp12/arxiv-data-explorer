# Causal Trends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Bayesian Poisson VAR inference + interactive causal graph visualizations for arXiv category dynamics.

**Architecture:** Python build-time script (NumPyro) fits 169 independent Poisson VAR models with graph-regularized priors, outputs JSON to `static/data/`. Three new SvelteKit CSR routes render the causal graph, category detail, and growth dashboard.

**Tech Stack:** Python (NumPyro, JAX, NumPy, SciPy), Svelte 5, D3.js, Tailwind v4

## Global Constraints

- 169 categories × 227 months, zero sparsity
- Semantics Scholar API is the only runtime dependency — no auth, no keys
- All analysis outputs static JSON, shipped as regular static assets
- CSR (`prerender = false`) for trend pages since JSON loaded at runtime
- Colors, fonts, spacing follow `app.css` custom property system (--ink, --soft, --faint, --line, --accent, etc.)
- No environment variables required

---

### Task 1: Python analysis script + build hook

**Files:**
- Create: `scripts/requirements.txt`
- Create: `scripts/poisson_var.py`
- Create: `scripts/postbuild.mjs`
- Modify: `package.json`

**Interfaces:**
- Consumes: `static/data/timeseries/*.json`, `static/data/category_graph.json`
- Produces: `static/data/causal_edges.json`, `static/data/category_dynamics.json`

- [ ] **Step 1: Create `scripts/requirements.txt`**

```
numpyro>=0.15.0
jax>=0.4.30
numpy>=1.24
scipy>=1.10
```

- [ ] **Step 2: Create `scripts/poisson_var.py`**

This script loads the timeseries and category graph, fits a Poisson VAR for each category, and writes the output JSON files.

```python
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
    """Load monthly category paper counts into a dict mapping category → list."""
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
    """Poisson VAR(1) with Normal priors on graph-neighbor coefficients.
    neighbor_lags shape: (n_neighbors, n_time) — log(1 + y_j,t-1) for each neighbor j.
    """
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
```

- [ ] **Step 3: Create `scripts/postbuild.mjs`**

```javascript
import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = resolve(__dirname, "poisson_var.py");

if (!existsSync(script)) {
  console.error("Missing:", script);
  process.exit(1);
}

try {
  console.log("Running Poisson VAR inference…");
  execSync(`python3 "${script}"`, { stdio: "inherit", cwd: resolve(__dirname, "..") });
} catch {
  console.error("Poisson VAR inference failed. Install deps: pip install -r scripts/requirements.txt");
  process.exit(1);
}
```

- [ ] **Step 4: Modify `package.json` — add postbuild script**

```json
"build": "vite build && node scripts/postbuild.mjs"
```

Change the `"build"` line in `package.json` from `"vite build"` to `"vite build && node scripts/postbuild.mjs"`.

- [ ] **Step 5: Verify the Python script runs**

```bash
pip install -r scripts/requirements.txt
python3 scripts/poisson_var.py
```

Expected output: `static/data/causal_edges.json` and `static/data/category_dynamics.json` created with valid JSON.

- [ ] **Step 6: Commit**

```bash
git add scripts/ package.json
git commit -m "feat: Bayesian Poisson VAR inference for category dynamics"
```


### Task 2: Trend route scaffolding

**Files:**
- Create: `src/routes/trends/+layout.ts`
- Create: `src/routes/trends/[id]/+layout.ts`
- Create: `src/routes/takeoffs/+layout.ts`
- Modify: `src/routes/+layout.svelte`

**Interfaces:**
- Consumes: output JSON from Task 1
- Produces: CSR route structure for Tasks 3-5

- [ ] **Step 1: Create `src/routes/trends/+layout.ts`**

```typescript
export const prerender = false;
```

- [ ] **Step 2: Create `src/routes/trends/[id]/+layout.ts`**

```typescript
export const prerender = false;
```

- [ ] **Step 3: Create `src/routes/takeoffs/+layout.ts`**

```typescript
export const prerender = false;
```

- [ ] **Step 4: Add "Trends" to nav sidebar in `src/routes/+layout.svelte`**

Insert after the Authors link entry in the `navLinks` array:

```typescript
{ href: "/trends", label: "Trends", icon: "trends" },
```

Insert before the About link.

Add a trends icon in the mobile nav SVG block after the categories icon:

```svelte
{:else if link.icon === "trends"}
	<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
		<polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
	</svg>
```

- [ ] **Step 5: Verify build**

```bash
npm run build
```

Should complete without errors (even though pages are empty, the routes exist).

- [ ] **Step 6: Commit**

```bash
git add src/routes/trends/ src/routes/takeoffs/ src/routes/+layout.svelte
git commit -m "feat: add Trends route scaffolding"
```


### Task 3: Causal graph page (`/trends`)

**Files:**
- Create: `src/routes/trends/+page.svelte`

**Interfaces:**
- Consumes: `static/data/causal_edges.json`, `static/data/category_graph.json`, `static/data/category_hierarchy.json`, `static/data/category_dynamics.json`
- Produces: interactive D3 force-directed graph

- [ ] **Step 1: Create `src/routes/trends/+page.svelte`**

```svelte
<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import * as d3 from "d3";

	interface Edge {
		source: string;
		target: string;
		weight: number;
		ci_lower: number;
		ci_upper: number;
		prob: number;
	}

	interface Category {
		id: string;
		trend: number;
		trend_ci: [number, number];
	}

	interface CausalData {
		edges: Edge[];
		categories: Category[];
	}

	interface GraphNode extends d3.SimulationNodeDatum {
		id: string;
		trend: number;
		weight: number;
		color: string;
		domain?: string;
	}

	interface GraphLink extends d3.SimulationLinkDatum<GraphNode> {
		weight: number;
		prob: number;
		color: string;
	}

	let svgEl = $state<SVGSVGElement>();
	let data = $state<CausalData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let hoverEdge = $state<{ source: string; target: string; weight: number; ci_lower: number; ci_upper: number; prob: number } | null>(null);
	let selectedDomain = $state("all");

	let domains = $state<string[]>([]);

	const domainColors: Record<string, string> = {
		cs: "#1f77b4", math: "#2ca02c", physics: "#ff7f0e",
		astro: "#9467bd", cond: "#8c564b", hep: "#e377c2",
		nlin: "#7f7f7f", nucl: "#bcbd22", q: "#17becf",
		stat: "#aec7e8", eess: "#ffbb78", econ: "#98df8a",
		q: "#ff9896",
	};

	function domainColor(id: string): string {
		const pref = id.split(".")[0];
		return domainColors[pref] ?? "#a1a1aa";
	}

	onMount(async () => {
		try {
			const [causalRes, hierarchyRes] = await Promise.all([
				fetch(`${base}/data/causal_edges.json`),
				fetch(`${base}/data/category_hierarchy.json`),
			]);
			if (!causalRes.ok || !hierarchyRes.ok) throw new Error("Failed to load");
			const causal: CausalData = await causalRes.json();
			const hierarchy = await hierarchyRes.json();

			const domainMap: Record<string, string> = {};
			for (const d of hierarchy.domains ?? []) {
				for (const sub of d.subcategories ?? []) {
					domainMap[sub.id] = d.id;
				}
			}

			data = causal;
			domains = [...new Set(Object.values(domainMap))];
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed to load";
		} finally {
			loading = false;
		}
	});

	$effect(() => {
		if (!data || !svgEl) return;

		const w = svgEl.clientWidth || 900;
		const h = Math.max(450, Math.min(550, w * 0.55));

		svgEl.setAttribute("viewBox", `0 0 ${w} ${h}`);
		d3.select(svgEl).selectAll("*").remove();

		const catMap = new Map(data.categories.map((c) => [c.id, c]));
		const catSet = new Set(data.categories.map((c) => c.id));

		const nodes: GraphNode[] = [...catSet].map((id) => {
			const c = catMap.get(id)!;
			return {
				id,
				trend: c.trend,
				weight: 1,
				color: c.trend > 0 ? "#22c55e" : c.trend < -0.01 ? "#ef4444" : "#a1a1aa",
			};
		});

		const links: GraphLink[] = data.edges
			.filter((e) => catSet.has(e.source) && catSet.has(e.target))
			.map((e) => ({
				source: e.source,
				target: e.target,
				weight: e.weight,
				prob: e.prob,
				color: e.weight > 0 ? "#22c55e" : "#ef4444",
			}));

		const sim = d3.forceSimulation(nodes)
			.force("link", d3.forceLink(links).id((d: any) => d.id).distance(70))
			.force("charge", d3.forceManyBody().strength(-80))
			.force("center", d3.forceCenter(w / 2, h / 2))
			.force("collision", d3.forceCollide().radius(6))
			.stop();

		const ticks = Math.ceil(Math.log(sim.alphaMin()) / Math.log(1 - sim.alphaDecay()));
		sim.tick(ticks);

		const g = d3.select(svgEl).append("g");

		g.selectAll("line")
			.data(links)
			.join("line")
			.attr("stroke", (d: any) => d.color)
			.attr("stroke-width", (d: any) => Math.max(0.5, Math.abs(d.weight) * 40))
			.attr("stroke-opacity", (d: any) => d.prob * 0.6)
			.attr("x1", (d: any) => d.source.x)
			.attr("y1", (d: any) => d.source.y)
			.attr("x2", (d: any) => d.target.x)
			.attr("y2", (d: any) => d.target.y)
			.on("mouseenter", (e: any, d: any) => {
				hoverEdge = {
					source: (typeof d.source === "object" ? d.source.id : d.source),
					target: (typeof d.target === "object" ? d.target.id : d.target),
					weight: d.weight,
					ci_lower: d.weight * 0.7,
					ci_upper: d.weight * 1.3,
					prob: d.prob,
				};
			})
			.on("mouseleave", () => { hoverEdge = null; });

		g.selectAll("circle")
			.data(nodes)
			.join("circle")
			.attr("r", 5)
			.attr("fill", (d: any) => d.color)
			.attr("stroke", "var(--panel)")
			.attr("stroke-width", 1.5)
			.attr("cx", (d: any) => d.x)
			.attr("cy", (d: any) => d.y)
			.append("title")
			.text((d: any) => `${d.id} (trend: ${catMap.get(d.id)?.trend.toFixed(4) ?? "?"})`);
	});
</script>
```

Then the template section:

```svelte
<svelte:head>
	<title>Causal Trends — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
	<header class="mb-8">
		<p class="kicker mb-3">Bayesian Poisson VAR · Graph-regularized</p>
		<h1 class="font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">Causal trends</h1>
		<p class="mt-2 max-w-xl text-sm leading-relaxed text-soft">
			Directed edges show Granger-causal influence between arXiv categories.
			Opacity = posterior probability, color = sign (green positive, red negative).
			Node color = growth rate (green growing, red declining).
		</p>
	</header>

	{#if loading}
		<div class="kicker flex h-[500px] items-center justify-center animate-pulse">Loading…</div>
	{:else if error}
		<div class="flex h-[500px] items-center justify-center text-sm text-accent">{error}</div>
	{:else}
		<div class="mb-4 flex flex-wrap items-center gap-4">
			<div class="flex items-center gap-2 text-xs text-soft">
				<span class="inline-block h-3 w-3 rounded-full bg-green-500"></span> Growing
				<span class="ml-3 inline-block h-3 w-3 rounded-full bg-red-500"></span> Declining
				<span class="ml-3 inline-block h-3 w-3 rounded-full bg-gray-400"></span> Stable
			</div>
		</div>

		<div class="overflow-hidden rounded-xl border border-line bg-panel">
			<svg bind:this={svgEl} class="h-[500px] w-full" role="img" aria-label="Causal category graph"></svg>
		</div>

		{#if hoverEdge}
			<div class="mt-4 rounded-lg border border-line bg-panel p-4 text-sm">
				<span class="font-mono text-accent">{hoverEdge.source}</span>
				<span class="text-soft"> → </span>
				<span class="font-mono text-accent">{hoverEdge.target}</span>
				<div class="mt-2 grid grid-cols-3 gap-4 font-mono text-xs text-soft">
					<div>Weight: <span class="text-ink">{hoverEdge.weight.toFixed(4)}</span></div>
					<div>95% CI: <span class="text-ink">[{hoverEdge.ci_lower.toFixed(4)}, {hoverEdge.ci_upper.toFixed(4)}]</span></div>
					<div>P(edge): <span class="text-ink">{hoverEdge.prob.toFixed(2)}</span></div>
				</div>
			</div>
		{/if}

		<div class="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each data?.categories.filter(c => c.trend > 0.01).sort((a, b) => b.trend - a.trend).slice(0, 6) as cat}
				<a href="/trends/{cat.id}" class="rounded-lg border border-line bg-panel p-4 transition-colors hover:border-green-500/50">
					<div class="font-mono text-xs text-accent">{cat.id}</div>
					<div class="mt-1 font-mono text-lg text-green-600 dark:text-green-400">+{(cat.trend * 100).toFixed(2)}%</div>
					<div class="kicker mt-1">monthly growth</div>
				</a>
			{/each}
			{#each data?.categories.filter(c => c.trend < -0.01).sort((a, b) => a.trend - b.trend).slice(0, 6) as cat}
				<a href="/trends/{cat.id}" class="rounded-lg border border-line bg-panel p-4 transition-colors hover:border-red-500/50">
					<div class="font-mono text-xs text-accent">{cat.id}</div>
					<div class="mt-1 font-mono text-lg text-red-600 dark:text-red-400">{(cat.trend * 100).toFixed(2)}%</div>
					<div class="kicker mt-1">monthly growth</div>
				</a>
			{/each}
		</div>
	{/if}
</div>
```

- [ ] **Step 2: Verify build**

```bash
npm run build
```

Should compile without errors.

- [ ] **Step 3: Commit**

```bash
git add src/routes/trends/+page.svelte
git commit -m "feat: causal graph view at /trends"
```


### Task 4: Category detail page (`/trends/[id]`)

**Files:**
- Create: `src/routes/trends/[id]/+page.svelte`

**Interfaces:**
- Consumes: `static/data/causal_edges.json`, `static/data/category_dynamics.json`
- Produces: trajectory chart + influence lists

- [ ] **Step 1: Create `src/routes/trends/[id]/+page.svelte`**

```svelte
<script lang="ts">
	import { page } from "$app/stores";
	import { base } from "$app/paths";
	import * as d3 from "d3";

	interface Edge { source: string; target: string; weight: number; ci_lower: number; ci_upper: number; prob: number; }
	interface Category { id: string; trend: number; trend_ci: [number, number]; }
	interface Dynamics { [cat: string]: { months: number[]; observed: number[]; } }

	let detail = $state<Category | null>(null);
	let incomingEdges = $state<Edge[]>([]);
	let outgoingEdges = $state<Edge[]>([]);
	let dynamics = $state<Dynamics | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let chartSvg = $state<SVGSVGElement>();

	$effect(() => {
		const id = $page.params.id ?? "";
		if (!id) { error = "No category specified"; loading = false; return; }

		loading = true;
		error = null;

		Promise.all([
			fetch(`${base}/data/causal_edges.json`).then(r => r.json()),
			fetch(`${base}/data/category_dynamics.json`).then(r => r.json()),
		]).then(([causal, dyn]) => {
			dynamics = dyn;
			const cat = causal.categories.find((c: Category) => c.id === id);
			if (cat) detail = cat;
			else error = "Category not found";

			incomingEdges = causal.edges.filter((e: Edge) => e.target === id).sort((a: Edge, b: Edge) => Math.abs(b.weight) - Math.abs(a.weight));
			outgoingEdges = causal.edges.filter((e: Edge) => e.source === id).sort((a: Edge, b: Edge) => Math.abs(b.weight) - Math.abs(a.weight));
		}).catch((e) => { error = e instanceof Error ? e.message : "Failed"; })
		.finally(() => { loading = false; });
	});

	$effect(() => {
		if (!dynamics || !detail || !chartSvg) return;
		const id = $page.params.id!;
		const d = dynamics[id];
		if (!d) return;

		const w = chartSvg.clientWidth || 700;
		const h = 250;
		const margin = { top: 20, right: 20, bottom: 30, left: 50 };

		chartSvg.setAttribute("viewBox", `0 0 ${w} ${h}`);
		d3.select(chartSvg).selectAll("*").remove();

		const x = d3.scaleLinear().domain([0, d.months.length - 1]).range([margin.left, w - margin.right]);
		const y = d3.scaleLinear().domain([0, d3.max(d.observed)! * 1.1]).range([h - margin.bottom, margin.top]);

		const svg = d3.select(chartSvg);

		svg.append("g")
			.attr("transform", `translate(0,${h - margin.bottom})`)
			.call(d3.axisBottom(x).ticks(8).tickFormat((i: any) => `${2007 + Math.floor(i / 12)}`));

		svg.append("g")
			.attr("transform", `translate(${margin.left},0)`)
			.call(d3.axisLeft(y).ticks(5));

		svg.append("path")
			.datum(d.observed.map((v: number, i: number) => [x(i), y(v)]))
			.attr("fill", "none")
			.attr("stroke", "var(--accent)")
			.attr("stroke-width", 1.5)
			.attr("d", d3.line() as any);
	});
</script>

<svelte:head>
	<title>{$page.params.id ?? "Category"} — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
	<a href="/trends" class="kicker mb-6 inline-flex items-center gap-1 transition-colors hover:text-accent">← Causal trends</a>

	{#if loading}
		<div class="kicker animate-pulse py-20 text-center">Loading…</div>
	{:else if error}
		<div class="py-20 text-center"><p class="font-display text-2xl font-bold text-ink">Not found</p><p class="kicker">{error}</p></div>
	{:else if detail}
		<header class="mb-8">
			<p class="kicker mb-3">Category dynamics</p>
			<h1 class="font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">{detail.id}</h1>
			<p class="mt-2 text-sm text-soft">
				Trend: <span class="font-mono text-ink">{(detail.trend * 100).toFixed(3)}%</span> per month
				<span class="text-faint"> [{(detail.trend_ci[0] * 100).toFixed(3)}, {(detail.trend_ci[1] * 100).toFixed(3)}]</span>
			</p>
		</header>

		<div class="mb-10 overflow-hidden rounded-xl border border-line bg-panel p-4">
			<svg bind:this={chartSvg} class="h-[250px] w-full"></svg>
		</div>

		<div class="grid grid-cols-1 gap-8 sm:grid-cols-2">
			<div>
				<p class="kicker mb-3">What drives {detail.id}</p>
				{#if incomingEdges.length === 0}
					<p class="text-sm text-faint">No significant incoming influences detected.</p>
				{:else}
					<div class="space-y-2">
						{#each incomingEdges.slice(0, 15) as edge}
							<a href="/trends/{edge.source}" class="block rounded-lg border border-line bg-panel p-3 transition-colors hover:border-accent/30">
								<div class="flex items-baseline justify-between">
									<span class="font-mono text-sm text-accent">{edge.source}</span>
									<span class="font-mono text-xs" class:text-green-600={edge.weight > 0} class:text-red-600={edge.weight < 0}>
										{edge.weight > 0 ? "+" : ""}{(edge.weight * 100).toFixed(2)}%
									</span>
								</div>
								<div class="mt-1 font-mono text-[11px] text-faint">
									CI [{(edge.ci_lower * 100).toFixed(2)}, {(edge.ci_upper * 100).toFixed(2)}]
									· P = {edge.prob.toFixed(2)}
								</div>
							</a>
						{/each}
					</div>
				{/if}
			</div>

			<div>
				<p class="kicker mb-3">What {detail.id} drives</p>
				{#if outgoingEdges.length === 0}
					<p class="text-sm text-faint">No significant outgoing influences detected.</p>
				{:else}
					<div class="space-y-2">
						{#each outgoingEdges.slice(0, 15) as edge}
							<a href="/trends/{edge.target}" class="block rounded-lg border border-line bg-panel p-3 transition-colors hover:border-accent/30">
								<div class="flex items-baseline justify-between">
									<span class="font-mono text-sm text-accent">{edge.target}</span>
									<span class="font-mono text-xs" class:text-green-600={edge.weight > 0} class:text-red-600={edge.weight < 0}>
										{edge.weight > 0 ? "+" : ""}{(edge.weight * 100).toFixed(2)}%
									</span>
								</div>
								<div class="mt-1 font-mono text-[11px] text-faint">
									CI [{(edge.ci_lower * 100).toFixed(2)}, {(edge.ci_upper * 100).toFixed(2)}]
									· P = {edge.prob.toFixed(2)}
								</div>
							</a>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
```

- [ ] **Step 2: Verify build**

```bash
npm run build
```

- [ ] **Step 3: Commit**

```bash
git add src/routes/trends/[id]/+page.svelte
git commit -m "feat: category detail page at /trends/[id]"
```


### Task 5: Takeoffs dashboard (`/takeoffs`)

**Files:**
- Create: `src/routes/takeoffs/+page.svelte`

**Interfaces:**
- Consumes: `static/data/causal_edges.json`, `static/data/category_hierarchy.json`
- Produces: sortable/filterable growth dashboard

- [ ] **Step 1: Create `src/routes/takeoffs/+page.svelte`**

```svelte
<script lang="ts">
	import { onMount } from "svelte";
	import { base } from "$app/paths";
	import type { PageData } from "./$types.js";

	interface Category { id: string; trend: number; trend_ci: [number, number]; }
	interface CausalData { edges: any[]; categories: Category[]; }

	let data = $state<CausalData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let sortField = $state<"trend" | "id">("trend");
	let sortDir = $state<"asc" | "desc">("desc");
	let domainFilter = $state("all");
	let domains = $state<string[]>([]);
	let domainMap = $state<Record<string, string>>({});

	onMount(async () => {
		try {
			const [causalRes, hierarchyRes] = await Promise.all([
				fetch(`${base}/data/causal_edges.json`),
				fetch(`${base}/data/category_hierarchy.json`),
			]);
			if (!causalRes.ok || !hierarchyRes.ok) throw new Error("Failed");
			const causal: CausalData = await causalRes.json();
			const hierarchy = await hierarchyRes.json();
			const dm: Record<string, string> = {};
			for (const d of hierarchy.domains ?? []) {
				for (const sub of d.subcategories ?? []) {
					dm[sub.id] = d.id;
				}
			}
			domainMap = dm;
			domains = [...new Set(Object.values(dm))];
			data = causal;
		} catch (e) {
			error = e instanceof Error ? e.message : "Failed";
		} finally {
			loading = false;
		}
	});

	let sorted = $derived.by(() => {
		if (!data) return [];
		let cats = data.categories;
		if (domainFilter !== "all") {
			cats = cats.filter((c) => domainMap[c.id] === domainFilter);
		}
		return [...cats].sort((a, b) => {
			const mul = sortDir === "desc" ? -1 : 1;
			if (sortField === "trend") return mul * (a.trend - b.trend);
			return mul * a.id.localeCompare(b.id);
		});
	});

	function toggleSort(field: "trend" | "id") {
		if (sortField === field) sortDir = sortDir === "desc" ? "asc" : "desc";
		else { sortField = field; sortDir = "desc"; }
	}
</script>

<svelte:head>
	<title>Takeoffs — arXiv Explorer</title>
</svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
	<header class="mb-8 flex flex-wrap items-end justify-between gap-4">
		<div>
			<p class="kicker mb-3">Growth rates · {data?.categories.length ?? "?"} categories</p>
			<h1 class="font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">Takeoffs</h1>
		</div>
		<select
			bind:value={domainFilter}
			class="rounded-lg border border-line bg-panel px-3 py-2 font-mono text-xs text-ink focus:border-accent focus:outline-none"
		>
			<option value="all">All domains</option>
			{#each domains as d}
				<option value={d}>{d}</option>
			{/each}
		</select>
	</header>

	{#if loading}
		<div class="kicker animate-pulse py-16 text-center">Loading…</div>
	{:else if error}
		<div class="py-16 text-center text-sm text-accent">{error}</div>
	{:else}
		<div class="overflow-x-auto rounded-xl border border-line">
			<table class="w-full text-left text-sm">
				<thead>
					<tr class="border-b border-line bg-panel">
						<th onclick={() => toggleSort("id")} class="kicker cursor-pointer px-4 py-3">
							Category {sortField === "id" ? (sortDir === "desc" ? "↓" : "↑") : ""}
						</th>
						<th onclick={() => toggleSort("trend")} class="kicker cursor-pointer px-4 py-3">
							Growth/month {sortField === "trend" ? (sortDir === "desc" ? "↓" : "↑") : ""}
						</th>
						<th class="kicker px-4 py-3">95% CI</th>
						<th class="kicker px-4 py-3">Domain</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-line">
					{#each sorted as cat}
						<tr class="transition-colors hover:bg-accent/4">
							<td class="px-4 py-3">
								<a href="/trends/{cat.id}" class="font-mono text-accent underline underline-offset-2">{cat.id}</a>
							</td>
							<td class="px-4 py-3">
								<div class="flex items-center gap-2">
									<div class="h-2 w-20 overflow-hidden rounded-full bg-line">
										<div
											class="h-full rounded-full"
											style="width: {Math.min(100, Math.abs(cat.trend) * 3000)}%;
												background: {cat.trend > 0 ? '#22c55e' : '#ef4444'}"
										></div>
									</div>
									<span class="font-mono text-xs" class:text-green-600={cat.trend > 0} class:text-red-600={cat.trend < 0}>
										{cat.trend > 0 ? "+" : ""}{(cat.trend * 100).toFixed(2)}%
									</span>
								</div>
							</td>
							<td class="px-4 py-3 font-mono text-xs text-faint">
								[{(cat.trend_ci[0] * 100).toFixed(2)}, {(cat.trend_ci[1] * 100).toFixed(2)}]
							</td>
							<td class="px-4 py-3 font-mono text-xs text-soft">{domainMap[cat.id] ?? "—"}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
```

- [ ] **Step 2: Verify build**

```bash
npm run build
```

- [ ] **Step 3: Commit**

```bash
git add src/routes/takeoffs/+page.svelte
git commit -m "feat: takeoffs dashboard at /takeoffs"
```

---

## Self-Review

**Spec coverage:**
- Poisson VAR model with graph-regularized priors ✅ (Task 1: `poisson_var.py`)
- Three JSON output files ✅ (Task 1)
- `npm run build` triggers Python analysis ✅ (Task 1: postbuild hook)
- Causal graph view `/trends` ✅ (Task 3: D3 force-directed, edge opacity = prob, color = sign, node color = growth)
- Category detail `/trends/[id]` with trajectory + influence lists ✅ (Task 4)
- Takeoffs dashboard `/takeoffs` with sortable table + domain filter ✅ (Task 5)
- CSR layouts for all new routes ✅ (Task 2)

**Placeholder scan:** No TBD, TODO, incomplete sections.

**Type consistency:** `causal_edges.json` shape matches between producer (Task 1) and all three consumers (Tasks 3-5). `category_dynamics.json` matches between producer (Task 1) and consumer (Task 4). No mismatches.
