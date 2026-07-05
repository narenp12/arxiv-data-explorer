# arXiv Network Explorer

A pre-rendered SvelteKit 5 static site for exploring 3M+ arXiv papers. Features D3.js force-directed category graphs, author rankings, paper search, category hierarchy, and Bayesian causal trend inference.

### Pages

- **Home** — hero, stats band, interactive category co-occurrence network
- **Papers** — search with Semantic Scholar API, paginated results
- **Authors** — ranked author list with paper counts
- **Categories** — domain/category hierarchy with color-coded indicators
- **Trends** — causal inference graph from Bayesian Poisson VAR (Granger causality between categories)

### Build

```bash
npm install
npm run build
```

The build pipeline runs a Bayesian Poisson VAR model (NumPyro/JAX) to compute causal category dynamics, outputting edge posteriors and category trends to `static/data/`.

### Packages

SvelteKit 5, D3.js, Tailwind CSS 4, TypeScript.  
Data pipeline: Polars, NumPyro/JAX, HuggingFace Hub.
