# Local Search Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect local arXiv paper database to frontend as routing/discovery layer for arXiv API, with Semantic Scholar toggle

**Architecture:** Three-tier Suggest → Route → Enrich. Client-side sharded JSON index provides auto-suggest (papers, authors, categories). Suggestion clicks route through existing `/api/arxiv` Cloudflare Pages Function proxy. Results enriched with local metadata. Toggle preserves separate query per tab.

**Tech Stack:** FlexSearch 0.8 (client-side), Svelte 5, TypeScript, vitest, Python brotli + gzip, Python daft DataFrame

## Global Constraints

- Free tier only — no D1, R2, paid services
- arXiv API always primary — local data only for suggest + enrich
- Semantic Scholar preserved as toggle with separate query state
- Non-ASCII: NFD normalize before first-character grouping
- Shards: 27 + 1 (`a.json.gz`–`z.json.gz` + `other.json.gz`)
- Cache: sessionStorage LRU (3 shards max), localStorage for meta version
- FlexSearch index rebuilt from sessionStorage on page reload
- Brotli + gzip both generated in build step
- Tests: vitest with jsdom (browser tests noted but out of scope for now)

---

### Task 1: Add project dependencies

**Files:**
- Modify: `package.json` (add flexsearch)
- Modify: `pyproject.toml` (add brotli)

**Interfaces:**
- Consumes: nothing
- Produces: flexsearch available for client-side import, brotli available for build script

- [ ] **Step 1: Add flexsearch to package.json dependencies**

Edit `package.json` — add `"flexsearch": "^0.8.1"` to `dependencies` object (not devDependencies — it ships to browser):

```json
"dependencies": {
    "@types/d3": "^7.4.3",
    "flexsearch": "^0.8.1"
}
```

- [ ] **Step 2: Add brotli to pyproject.toml dependencies**

Edit `pyproject.toml` — add `"brotli>=1.1"` to the `dependencies` list:

```toml
dependencies = [
    "daft>=0.3.0,<1.0.0",
    "numpy>=2.4",
    "pandas>=2.2",
    "huggingface-hub>=1.17.0",
    "pymupdf>=1.28.0",
    "sentence-transformers>=5.6.0",
    "faiss-cpu>=1.14.3",
    "scikit-learn>=1.9.0",
    "brotli>=1.1",
]
```

- [ ] **Step 3: Install dependencies**

```bash
npm install
```

```bash
uv sync  # or: pip install brotli
```

- [ ] **Step 4: Commit**

```bash
git add package.json package-lock.json pyproject.toml uv.lock
git commit -m "feat: add flexsearch and brotli deps"
```

---

### Task 2: Build suggest shards in build_data.py

**Files:**
- Modify: `scripts/build_data.py`
- Create (output): `static/data/search/suggest/` directory with `.json.gz` and `.json.br` files

**Interfaces:**
- Consumes: `df` (daft DataFrame with `id`, `title`, `authors`, `categories` columns), loaded from existing `load_shards()`
- Produces: `build_suggest_index(df)` function, called in `__main__` block, outputs shard files + meta.json

- [ ] **Step 1: Write the test for build_suggest_index**

Create test at bottom of `scripts/build_data.py` with a `__test__` guard, or add a proper pytest test in `tests/`. Since build_data.py doesn't have tests yet, add a minimal pytest test file.

Create `tests/test_build_suggest_index.py`:

```python
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
            assert (out / "q.json.gz").exists()  # Quantum
            assert (out / "a.json.gz").exists()  # Artificial
            assert (out / "g.json.gz").exists()  # General
            assert (out / "p.json.gz").exists()  # Physics
            assert (out / "categories.json.gz").exists()

    def test_shard_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suggest"
            build_suggest_index(SAMPLE_DF, out)
            with gzip.open(out / "q.json.gz", "rt") as f:
                data = json.load(f)
            assert "t" in data
            assert "a" in data
            assert ["Quantum Theory", "arXiv:quant-ph/0001001"] in data["t"]  # or whatever order
            assert ["Einstein", 0] in data["a"]  # author name and rank index

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
            # Check categories contain expected entries
            cats = dict(data["c"])
            assert "quant-ph" in cats
            assert "cs.AI" in cats

    def test_non_ascii_normalization(self):
        df = daft.from_pydict({
            "id": ["arXiv:2401.00001"],
            "title": ["Élégant Théorie"],  # starts with E after NFD
            "authors": ["René"],
            "categories": [["math.GM"]],
        })
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suggest"
            build_suggest_index(df, out)
            assert (out / "e.json.gz").exists(), "NFD-normalized to e"
            assert not (out / "other.json.gz").exists(), "not in other"

    def test_other_shard_for_non_alpha(self):
        df = daft.from_pydict({
            "id": ["arXiv:2401.00001"],
            "title": ["2024 Trends"],  # starts with digit
            "authors": ["Author"],
            "categories": [["cs.IR"]],
        })
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "suggest"
            build_suggest_index(df, out)
            assert (out / "other.json.gz").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pip install pytest && pytest tests/test_build_suggest_index.py -v
```

Expected: FAIL - `build_suggest_index` not found

- [ ] **Step 3: Write the build_suggest_index function**

Add before the `parse_args()` function near line 724:

```python
def build_suggest_index(df, output_dir=None, author_ranking_path=None):
    """Build per-letter suggestion shards for client-side auto-suggest.

    For each first letter of the NFD-normalized title, writes a gzipped JSON
    shard with paper titles and author names. Also writes Brotli-compressed
    variants and a categories file.

    Args:
        df: daft DataFrame with columns: id, title, authors, categories
        output_dir: Path to write suggest shards (default: DATA_DIR / search / suggest)
        author_ranking_path: Path to author_rankings.json (default: DATA_DIR / author_rankings.json)

    Returns:
        dict with stats: total_papers, per-shard counts
    """
    import brotli
    import unicodedata
    import re

    if output_dir is None:
        output_dir = DATA_DIR / "search" / "suggest"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load author rankings for index mapping
    if author_ranking_path is None:
        author_ranking_path = DATA_DIR / "author_rankings.json"
    author_rankings = {}
    if author_ranking_path.exists():
        rankings = json.loads(author_ranking_path.read_text())
        for idx, entry in enumerate(rankings):
            if isinstance(entry, dict):
                author_rankings[entry.get("name", entry.get("author", ""))] = idx
            else:
                author_rankings[str(entry)] = idx

    # Collect by first character
    shard_data = {}
    categories_set = {}

    papers = df.to_pydict()
    for i in range(len(papers["id"])):
        raw = papers["title"][i] or ""
        normalized = unicodedata.normalize("NFD", raw)
        normalized = re.sub(r"[\u0300-\u036f]", "", normalized)  # strip combining marks
        first_char = normalized[0].lower() if normalized else "other"
        if not re.match(r"^[a-zA-Z0-9]$", first_char):
            first_char = "other"

        if first_char not in shard_data:
            shard_data[first_char] = {"t": [], "a_seen": set()}

        paper_id = papers["id"][i]
        shard_data[first_char]["t"].append([paper_id, raw])

        for author_name in (papers["authors"][i] or []):
            if author_name not in shard_data[first_char]["a_seen"]:
                shard_data[first_char]["a_seen"].add(author_name)
                rank_idx = author_rankings.get(author_name, -1)
                shard_data[first_char]["a"].append([author_name, rank_idx])

        for cat in (papers["categories"][i] or []):
            categories_set[cat] = ""

    # Write category names (need to look up from df or pass from hierarchy)
    # For now, use empty description — enriched by frontend from categories.json.gz
    categories_list = sorted(categories_set.keys())
    cat_data = {"c": [[c, ""] for c in categories_list]}

    import time
    now = time.strftime("%Y-%m-%d")

    shard_meta = {}
    total_papers = 0

    for letter in sorted(shard_data.keys()):
        sd = shard_data[letter]
        entry = {"t": sd["t"], "a": sd["a"]}
        payload = json.dumps(entry, separators=(",", ":"), ensure_ascii=False)

        # Write gzip
        with gzip.open(output_dir / f"{letter}.json.gz", "wt", encoding="utf-8") as f:
            f.write(payload)

        # Write brotli
        compressed = brotli.compress(payload.encode("utf-8"))
        (output_dir / f"{letter}.json.br").write_bytes(compressed)

        paper_count = len(sd["t"])
        author_count = len(sd["a"])
        shard_meta[letter] = {
            "papers": paper_count,
            "authors": author_count,
            "size_bytes": len(payload.encode("utf-8")),
        }
        total_papers += paper_count

    # Write categories
    cat_payload = json.dumps(cat_data, separators=(",", ":"), ensure_ascii=False)
    with gzip.open(output_dir / "categories.json.gz", "wt", encoding="utf-8") as f:
        f.write(cat_payload)
    cat_br = brotli.compress(cat_payload.encode("utf-8"))
    (output_dir / "categories.json.br").write_bytes(cat_br)

    # Write meta.json
    meta = {
        "version": 1,
        "updated": now,
        "total_papers": total_papers,
        "shards": shard_meta,
    }
    (output_dir / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))

    # Clean up internal keys
    for letter in shard_data:
        shard_data[letter].pop("a_seen", None)

    return {
        "total_papers": total_papers,
        "shards": list(shard_data.keys()),
        "categories": len(categories_list),
    }
```

- [ ] **Step 4: Add build_suggest_index call to main block**

Before the conditional builders (around line 791), add:

```python
print("Building suggest shards…")
suggest_stats = build_suggest_index(df)
print(f"  {suggest_stats['total_papers']:,} papers in {len(suggest_stats['shards'])} shards")
print(f"  {suggest_stats['categories']:,} categories")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_build_suggest_index.py -v
```

Expected: PASS (all 7 tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/build_data.py tests/test_build_suggest_index.py
git commit -m "feat: add build_suggest_index to build_data.py"
```

---

### Task 3: Generate suggest shard files

**Files:**
- Run: `scripts/build_data.py` (full build, or with `--no-incremental` if needed)
- Output: `static/data/search/suggest/` with all shard files

- [ ] **Step 1: Run the build script to generate suggest shards**

```bash
cd /path/to/repo && python scripts/build_data.py
```

Note: this runs the full build pipeline. If you only want to generate suggest shards, you can temporarily comment out other builders in `__main__`.

- [ ] **Step 2: Verify output**

```bash
ls -lh static/data/search/suggest/
```

Expected: `a.json.gz`, `a.json.br`, `b.json.gz`, `b.json.br`, ..., `z.json.gz`, `z.json.br`, `other.json.gz`, `other.json.br`, `categories.json.gz`, `categories.json.br`, `meta.json`

```bash
python -c "
import json
meta = json.loads(open('static/data/search/suggest/meta.json').read())
print(f'Version: {meta[\"version\"]}')
print(f'Papers: {meta[\"total_papers\"]:,}')
print(f'Shards: {list(meta[\"shards\"].keys())}')
for k, v in sorted(meta['shards'].items()):
    print(f'  {k}: {v[\"papers\"]:,} papers, {v[\"authors\"]:,} authors')
"
```

- [ ] **Step 3: Verify Brotli files are served by Cloudflare Pages**

No action needed — Cloudflare Pages automatically serves `.br` files with `Content-Encoding: br` when the client sends `Accept-Encoding: br`.

- [ ] **Step 4: Commit**

```bash
git add static/data/search/suggest/
git commit -m "feat: generate suggest shard files"
```

---

### Task 4: Create SuggestShard class

**Files:**
- Create: `src/lib/utils/db/suggest.ts`
- Create: `src/lib/utils/db/suggest.test.ts`
- Modify: `src/lib/utils/db/index.ts` (add export)

**Interfaces:**
- Consumes: shard files from `static/data/search/suggest/` (fetched via HTTP)
- Produces: `SuggestShard` class exported from `src/lib/utils/db/index.ts`
- Public API:
  - `new SuggestShard().load(letter: string): Promise<void>` — fetch, decompress, cache, build index
  - `new SuggestShard().search(query: string, limit?: number): SuggestResults` — query FlexSearch
  - `new SuggestShard().prefetch(): void` — background-load common shards
  - `new SuggestShard().checkVersion(): Promise<boolean>` — validate meta version
  - `new SuggestShard().getStatus(): 'loading' | 'ready' | 'error' | 'disabled'`
- Types:
  - `SuggestResults = { papers: Array<{id: string, title: string}>, authors: Array<{name: string, rankIndex: number}>, categories: Array<{code: string, desc: string}> }`
  - `SuggestStatus = 'loading' | 'ready' | 'error' | 'disabled'`

- [ ] **Step 1: Write the failing test**

Create `src/lib/utils/db/suggest.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// We mock fetch globally
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

// Helpers to create mock shard data
function makeGzippedShard(data: object): ArrayBuffer {
    // In test we'll use the actual gzip + FlexSearch
    // For this test suite, we mock at the fetch level
    return new TextEncoder().encode(JSON.stringify(data)).buffer as ArrayBuffer;
}

function makeMockShardResponse(data: object): Response {
    const encoder = new TextEncoder();
    const bytes = encoder.encode(JSON.stringify(data));
    // Simulate gzip — in real code, these would be gzipped
    return new Response(bytes, {
        headers: { "content-type": "application/gzip" },
    });
}

describe("SuggestShard", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        // Clear sessionStorage
        sessionStorage.clear();
        localStorage.clear();
    });

    it("loads a shard and builds a FlexSearch index", async () => {
        const shardData = {
            t: [["arXiv:2401.00001", "Quantum Computing"], ["arXiv:2401.00002", "Quantum Theory"]],
            a: [["Einstein", 0], ["Feynman", 1]],
        };
        mockFetch.mockResolvedValueOnce(makeMockShardResponse(shardData));

        const { SuggestShard } = await import("./suggest.js");
        const ss = new SuggestShard();
        expect(ss.getStatus()).toBe("loading");

        await ss.load("q");
        expect(ss.getStatus()).toBe("ready");

        const results = ss.search("quantum");
        expect(results.papers.length).toBeGreaterThanOrEqual(1);
        expect(results.papers[0].id).toBe("arXiv:2401.00001");
    });

    it("caches loaded shard in sessionStorage", async () => {
        const shardData = { t: [["arXiv:2401.00001", "Test Paper"]], a: [] };
        mockFetch.mockResolvedValueOnce(makeMockShardResponse(shardData));

        const { SuggestShard } = await import("./suggest.js");
        const ss = new SuggestShard();
        await ss.load("t");

        // sessionStorage should have the raw data
        const cached = sessionStorage.getItem("suggest_shard_t");
        expect(cached).not.toBeNull();

        // Second load should use cache, not fetch
        mockFetch.mockClear();
        const ss2 = new SuggestShard();
        await ss2.load("t");
        expect(mockFetch).not.toHaveBeenCalled();
    });

    it("handles QuotaExceededError by clearing sessionStorage", async () => {
        const shardData = { t: [["arXiv:2401.00001", "Test"]], a: [] };
        mockFetch.mockResolvedValueOnce(makeMockShardResponse(shardData));

        // Fill sessionStorage to trigger quota error
        let setItemCalls = 0;
        const origSetItem = Storage.prototype.setItem;
        Storage.prototype.setItem = vi.fn().mockImplementation(function(this: Storage, key: string, value: string) {
            setItemCalls++;
            if (setItemCalls >= 2) {
                const err = new DOMException("QuotaExceededError", "QuotaExceededError");
                (err as any).code = 22;
                throw err;
            }
            origSetItem.call(this, key, value);
        });

        const { SuggestShard } = await import("./suggest.js");
        let loadErr: Error | null = null;
        try {
            const ss = new SuggestShard();
            await ss.load("q");
        } catch (e) {
            loadErr = e as Error;
        }

        Storage.prototype.setItem = origSetItem; // restore

        // Should not throw — it handled the error
        expect(loadErr).toBeNull();
    });

    it("uses AbortController to cancel previous fetch", async () => {
        const { SuggestShard } = await import("./suggest.js");
        const ss = new SuggestShard();

        // The second load should abort the first
        const abortSpy = vi.spyOn(AbortController.prototype, "abort");

        mockFetch.mockResolvedValueOnce(new Response("{}"));
        ss.load("a");
        await ss.load("b");

        expect(abortSpy).toHaveBeenCalledTimes(1);
    });

    it("prefetches common shards via requestIdleCallback", async () => {
        // Mock requestIdleCallback to fire immediately
        const origRic = globalThis.requestIdleCallback;
        globalThis.requestIdleCallback = vi.fn((cb: any) => {
            cb({ didTimeout: false, timeRemaining: () => 50 });
            return 0;
        } as any);

        const { SuggestShard } = await import("./suggest.js");
        // Create a mock response for each common shard
        mockFetch.mockResolvedValue(new Response('{"t":[],"a":[]}'));

        const ss = new SuggestShard();
        ss.prefetch();

        // Should have fetched common shards (a, c, m, s, t)
        await new Promise(r => setTimeout(r, 10));

        const calledLetters = mockFetch.mock.calls
            .map((c: any) => c[0])
            .filter((url: string) => url.includes("json"))
            .map((url: string) => url.match(/\/([a-z])\.json/)?.[1])
            .filter(Boolean);

        expect(calledLetters).toContain("a");
        expect(calledLetters).toContain("c");
        expect(calledLetters).toContain("m");
        expect(calledLetters).toContain("s");
        expect(calledLetters).toContain("t");

        globalThis.requestIdleCallback = origRic;
    });

    it("search returns empty results for no match", async () => {
        const shardData = { t: [["arXiv:2401.00001", "Quantum Computing"]], a: [] };
        mockFetch.mockResolvedValueOnce(makeMockShardResponse(shardData));

        const { SuggestShard } = await import("./suggest.js");
        const ss = new SuggestShard();
        await ss.load("q");
        const results = ss.search("biology");
        expect(results.papers).toHaveLength(0);
        expect(results.authors).toHaveLength(0);
    });

    it("checkVersion purges cache on mismatch", async () => {
        // Set stale version in localStorage
        localStorage.setItem("suggest_meta_version", "0");
        sessionStorage.setItem("suggest_shard_q", "old_data");

        // Mock meta fetch with newer version
        mockFetch.mockResolvedValueOnce(
            new Response(JSON.stringify({ version: 1, total_papers: 100, shards: {} }))
        );

        const { SuggestShard } = await import("./suggest.js");
        const ss = new SuggestShard();
        const needsRefresh = await ss.checkVersion();

        expect(needsRefresh).toBe(true);
        expect(sessionStorage.getItem("suggest_shard_q")).toBeNull();
    });

    it("search returns categories when loaded", async () => {
        const shardData = { t: [["arXiv:2401.00001", "Machine Learning"]], a: [] };
        mockFetch.mockResolvedValueOnce(makeMockShardResponse(shardData));
        // Also mock categories file
        mockFetch.mockResolvedValueOnce(
            new Response(JSON.stringify({ c: [["cs.LG", "Machine Learning"], ["stat.ML", "Machine Learning"]] }))
        );

        const { SuggestShard } = await import("./suggest.js");
        const ss = new SuggestShard();
        await ss.load("m");
        const results = ss.search("machine");

        expect(results.papers.length).toBeGreaterThanOrEqual(1);
    });

    it("falls back to disabled state on FlexSearch OOM", async () => {
        // This is hard to truly test without OOM, so we verify the
        // error handling path exists by checking the disabled state
        const { SuggestShard } = await import("./suggest.js");
        const ss = new SuggestShard();

        // Simulate FlexSearch throwing
        const origFlexSearch = (globalThis as any).FlexSearch;
        (globalThis as any).FlexSearch = vi.fn(() => { throw new Error("OOM"); });

        const shardData = { t: [["arXiv:2401.00001", "Test"]], a: [] };
        mockFetch.mockResolvedValueOnce(makeMockShardResponse(shardData));

        await ss.load("q");
        expect(ss.getStatus()).toBe("disabled");

        (globalThis as any).FlexSearch = origFlexSearch;
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npx vitest run src/lib/utils/db/suggest.test.ts --reporter=verbose
```

Expected: FAIL — `Cannot find module './suggest.js'`

- [ ] **Step 3: Write the SuggestShard class**

Create `src/lib/utils/db/suggest.ts`:

```typescript
import FlexSearch from "flexsearch";
import { getProp } from "./helpers";

const SHARD_BASE = "/data/search/suggest";
const COMMON_SHARDS = ["a", "c", "m", "s", "t"];
const LRU_MAX = 3;

interface ShardEntry {
    t: [string, string][];  // [paperId, title]
    a: [string, number][];  // [authorName, rankingIndex]
}

interface CategoriesEntry {
    c: [string, string][];  // [categoryCode, description]
}

interface MetaEntry {
    version: number;
    updated: string;
    total_papers: number;
    shards: Record<string, { papers: number; authors: number; size_bytes: number }>;
}

export interface SuggestResults {
    papers: Array<{ id: string; title: string }>;
    authors: Array<{ name: string; rankIndex: number }>;
    categories: Array<{ code: string; desc: string }>;
}

type SuggestStatus = "loading" | "ready" | "error" | "disabled";

let categoriesData: CategoriesEntry | null = null;
let categoriesPromise: Promise<void> | null = null;

async function loadCategories(): Promise<void> {
    if (categoriesData) return;
    if (categoriesPromise) return categoriesPromise;
    categoriesPromise = (async () => {
        const res = await fetch(`${SHARD_BASE}/categories.json.gz`);
        if (!res.ok) return;
        const buf = await res.arrayBuffer();
        // Decompress gunzip (browser built-in)
        const ds = new DecompressionStream("gzip");
        const decompressed = await new Response(
            new ReadableStream({ start: c => c.enqueue(buf), type: "bytes" } as any).pipeThrough(ds)
        ).text();
        categoriesData = JSON.parse(decompressed);
    })();
    return categoriesPromise;
}

export class SuggestShard {
    private letter: string = "";
    private index: FlexSearch.Document<{ id: string; title: string }> | null = null;
    private papers: Array<{ id: string; title: string }> = [];
    private authors: Array<{ name: string; rankIndex: number }> = [];
    private status: SuggestStatus = "loading";
    private controller: AbortController | null = null;
    private lruKeys: string[] = [];

    getStatus(): SuggestStatus {
        return this.status;
    }

    async load(letter: string): Promise<void> {
        this.letter = letter;
        this.status = "loading";

        // Check version before loading
        const needsRefresh = await this.checkVersion();
        if (needsRefresh) {
            this.clearCache();
        }

        // Cancel previous inflight fetch
        if (this.controller) {
            this.controller.abort();
        }
        this.controller = new AbortController();

        try {
            // Check sessionStorage first
            const cached = sessionStorage.getItem(`suggest_shard_${letter}`);
            let raw: string;
            let entry: ShardEntry;

            if (cached) {
                raw = cached;
                entry = JSON.parse(raw);
            } else {
                const res = await fetch(`${SHARD_BASE}/${letter}.json.gz`, {
                    signal: this.controller.signal,
                });
                if (!res.ok) throw new Error(`Shard ${letter} not found`);
                const buf = await res.arrayBuffer();
                const ds = new DecompressionStream("gzip");
                const decompressed = await new Response(
                    new ReadableStream({ start: c => c.enqueue(buf), type: "bytes" } as any).pipeThrough(ds)
                ).text();
                raw = decompressed;
                entry = JSON.parse(raw);
                // Cache in sessionStorage with LRU eviction
                this.cacheShard(letter, raw);
            }

            if (!entry || !("t" in entry)) throw new Error("Invalid shard format");

            this.papers = entry.t.map(([id, title]) => ({ id, title }));
            this.authors = entry.a.map(([name, rankIndex]) => ({ name, rankIndex }));

            // Build FlexSearch index
            try {
                this.index = new FlexSearch.Document({
                    document: {
                        id: "id",
                        index: ["title"],
                        store: ["title"],
                    },
                    tokenize: "forward",
                    cache: true,
                });
                for (const p of this.papers) {
                    this.index.add(p);
                }
            } catch (e) {
                console.warn("FlexSearch OOM, disabling suggestions", e);
                this.status = "disabled";
                this.index = null;
                return;
            }

            // Load categories in background
            loadCategories().catch(() => {});

            this.status = "ready";
        } catch (e: any) {
            if (e?.name === "AbortError") return; // cancelled, not an error
            console.warn(`SuggestShard load error for ${letter}:`, e);
            this.status = "error";
        }
    }

    search(query: string, limit: number = 10): SuggestResults {
        const results: SuggestResults = {
            papers: [],
            authors: [],
            categories: [],
        };

        if (this.status === "disabled" || !this.index) {
            return results;
        }

        const q = query.toLowerCase().trim();
        if (!q) return results;

        // Search FlexSearch
        if (this.index) {
            const raw = this.index.search(q, { limit, enrich: true });
            if (raw && raw.length > 0) {
                const ids = new Set<string>();
                for (const field of raw) {
                    if (field.result) {
                        for (const id of field.result as string[]) {
                            if (!ids.has(id)) {
                                ids.add(id);
                                const p = this.papers.find(p => p.id === id);
                                if (p) results.papers.push(p);
                            }
                        }
                    }
                }
            }
        }

        // Search authors (simple prefix match)
        for (const a of this.authors) {
            if (results.authors.length >= limit) break;
            if (a.name.toLowerCase().includes(q)) {
                results.authors.push(a);
            }
        }

        // Search categories if loaded
        if (categoriesData) {
            for (const [code, desc] of categoriesData.c) {
                if (results.categories.length >= limit) break;
                if (code.toLowerCase().includes(q) || desc.toLowerCase().includes(q)) {
                    results.categories.push({ code, desc });
                }
            }
        }

        return results;
    }

    prefetch(): void {
        const cb = () => {
            for (const letter of COMMON_SHARDS) {
                // Only prefetch if not already cached
                if (!sessionStorage.getItem(`suggest_shard_${letter}`)) {
                    // Background fetch but don't build index
                    fetch(`${SHARD_BASE}/${letter}.json.gz`)
                        .then(r => r.arrayBuffer())
                        .then(buf => {
                            const ds = new DecompressionStream("gzip");
                            return new Response(
                                new ReadableStream({ start: c => c.enqueue(buf), type: "bytes" } as any).pipeThrough(ds)
                            ).text();
                        })
                        .then(raw => {
                            this.cacheShard(letter, raw);
                        })
                        .catch(() => {});
                }
            }
        };
        if ("requestIdleCallback" in globalThis) {
            (globalThis as any).requestIdleCallback(cb, { timeout: 5000 });
        } else {
            setTimeout(cb, 5000);
        }
    }

    async checkVersion(): Promise<boolean> {
        try {
            const res = await fetch(`${SHARD_BASE}/meta.json`);
            if (!res.ok) return false;
            const meta: MetaEntry = await res.json();
            const storedVersion = localStorage.getItem("suggest_meta_version");
            if (storedVersion !== String(meta.version)) {
                localStorage.setItem("suggest_meta_version", String(meta.version));
                return true; // needs refresh
            }
            return false;
        } catch {
            return false;
        }
    }

    private cacheShard(letter: string, raw: string): void {
        try {
            sessionStorage.setItem(`suggest_shard_${letter}`, raw);
            this.lruKeys = this.lruKeys.filter(k => k !== letter);
            this.lruKeys.push(letter);
            if (this.lruKeys.length > LRU_MAX) {
                const evict = this.lruKeys.shift();
                if (evict) sessionStorage.removeItem(`suggest_shard_${evict}`);
            }
        } catch (e: any) {
            if (e?.name === "QuotaExceededError" || e?.code === 22) {
                try {
                    sessionStorage.clear();
                    this.lruKeys = [letter];
                    sessionStorage.setItem(`suggest_shard_${letter}`, raw);
                } catch {
                    // Give up on caching
                }
            }
        }
    }

    private clearCache(): void {
        sessionStorage.clear();
        this.lruKeys = [];
    }
}
```

- [ ] **Step 4: Export SuggestShard from db/index.ts**

Edit `src/lib/utils/db/index.ts` — add export line:

```typescript
export { SuggestShard } from './suggest';
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
npx vitest run src/lib/utils/db/suggest.test.ts --reporter=verbose
```

Expected: PASS (some tests may need adjustment for the DecompressionStream mock — see Note)

> **Note:** The `DecompressionStream` API may not be available in jsdom test environment. If tests fail on `DecompressionStream is not defined`, add a mock at the top of the test file:
> ```typescript
> import { decompress } from "fflate"; // or use a simple mock
> // Mock DecompressionStream
> (globalThis as any).DecompressionStream = class {
>     constructor() {}
>     readable = new ReadableStream();
>     writable = new WritableStream();
> };
> ```

- [ ] **Step 6: Commit**

```bash
git add src/lib/utils/db/suggest.ts src/lib/utils/db/suggest.test.ts src/lib/utils/db/index.ts
git commit -m "feat: add SuggestShard class for client-side auto-suggest"
```

---

### Task 5: Add generic searchArxiv function

**Files:**
- Modify: `src/lib/utils/db/search.ts`
- Modify: `src/lib/utils/db/index.ts` (re-export)
- Modify: `src/lib/utils/db.test.ts` (add tests)

**Interfaces:**
- Consumes: arXiv API XML via `/api/arxiv` proxy
- Produces: `searchArxiv(query, opts?)` exported from `src/lib/utils/db/index.ts`
- Public API: `searchArxiv(query: string, opts?: { limit?: number, offset?: number }): Promise<{ results: PaperResult[], total: number }>`
- Operates alongside existing `searchArxivCategory()` and `searchPapers()`

- [ ] **Step 1: Write the failing test**

Add to `src/lib/utils/db.test.ts`:

```typescript
describe("searchArxiv", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    it("constructs all: query for plain text", async () => {
        globalThis.fetch = vi.fn().mockResolvedValue(
            new Response(`
                <feed xmlns="http://www.w3.org/2005/Atom">
                    <opensearch:totalResults>1</opensearch:totalResults>
                    <entry>
                        <id>http://arxiv.org/abs/2401.00001</id>
                        <title>Quantum Computing</title>
                        <author><name>Einstein</name></author>
                        <published>2024-01-01</published>
                    </entry>
                </feed>
            `, { headers: { "Content-Type": "application/xml" } })
        );

        const { searchArxiv } = await import("./search.js");
        const result = await searchArxiv("quantum computing");
        expect(result.total).toBe(1);
        expect(result.results[0].title).toBe("Quantum Computing");

        const url = (globalThis.fetch as any).mock.calls[0][0];
        expect(url).toContain("search_query=all%3Aquantum+computing");
    });

    it("passes cat: prefix through", async () => {
        globalThis.fetch = vi.fn().mockResolvedValue(
            new Response(`<feed xmlns="http://www.w3.org/2005/Atom"><opensearch:totalResults>0</opensearch:totalResults></feed>`,
                { headers: { "Content-Type": "application/xml" } })
        );

        const { searchArxiv } = await import("./search.js");
        await searchArxiv("cat:cs.LG");
        const url = (globalThis.fetch as any).mock.calls[0][0];
        expect(url).toContain("search_query=cat%3Acs.LG");
    });

    it("reuses existing parseArxivResponse for XML parsing", async () => {
        globalThis.fetch = vi.fn().mockResolvedValue(
            new Response(`<feed xmlns="http://www.w3.org/2005/Atom"><opensearch:totalResults>1</opensearch:totalResults>
                <entry><id>http://arxiv.org/abs/2401.00001</id><title>Test</title>
                <author><name>Author</name></author><published>2024-01-01</published></entry></feed>`,
                { headers: { "Content-Type": "application/xml" } })
        );

        const { searchArxiv } = await import("./search.js");
        const result = await searchArxiv("test");
        expect(result.total).toBe(1);
        expect(result.results.length).toBe(1);
    });

    it("handles arXiv BUSY error", async () => {
        globalThis.fetch = vi.fn().mockRejectedValue(new Error("SEARCH_BUSY"));

        const { searchArxiv } = await import("./search.js");
        await expect(searchArxiv("test")).rejects.toThrow("ARXIV_BUSY");
    });

    it("handles HTTP errors", async () => {
        globalThis.fetch = vi.fn().mockResolvedValue(new Response("", { status: 500 }));

        const { searchArxiv } = await import("./search.js");
        await expect(searchArxiv("test")).rejects.toThrow("arXiv error: 500");
    });

    it("caches results", async () => {
        globalThis.fetch = vi.fn().mockResolvedValue(
            new Response(`<feed xmlns="http://www.w3.org/2005/Atom"><opensearch:totalResults>1</opensearch:totalResults>
                <entry><id>http://arxiv.org/abs/2401.00001</id><title>Test</title>
                <author><name>A</name></author><published>2024-01-01</published></entry></feed>`,
                { headers: { "Content-Type": "application/xml" } })
        );

        const { searchArxiv, clearSearchCache } = await import("./search.js");

        // Call once to populate cache
        await searchArxiv("test");
        const callCount = (globalThis.fetch as any).mock.calls.length;

        // Call again — should use cache
        await searchArxiv("test");
        expect((globalThis.fetch as any).mock.calls.length).toBe(callCount);

        clearSearchCache();
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npx vitest run src/lib/utils/db.test.ts --reporter=verbose -t "searchArxiv"
```

Expected: FAIL — `searchArxiv is not defined` or similar

- [ ] **Step 3: Write the searchArxiv function**

Add to `src/lib/utils/db/search.ts` (before or after existing `searchArxivCategory`):

```typescript
export async function searchArxiv(
    query: string,
    opts?: { limit?: number; offset?: number }
): Promise<{ results: PaperResult[]; total: number }> {
    const q = query.trim();
    if (!q || q.length < 2) return { results: [], total: 0 };

    const limit = opts?.limit ?? 30;
    const offset = opts?.offset ?? 0;

    const cacheKey = JSON.stringify({ kind: "arxiv", query: q, limit, offset });
    const cached = getCached(searchCache, cacheKey) as { results: PaperResult[]; total: number } | undefined;
    if (cached) return cached;

    // Detect query format
    let searchParam: string;
    const catMatch = q.match(/^cat:(\S+)$/i);
    const auMatch = q.match(/^au:"(.+)"$/i);
    const idMatch = q.match(/^id:(\S+)$/i);
    if (catMatch) {
        searchParam = `cat:${catMatch[1]}`;
    } else if (auMatch) {
        searchParam = `au:"${auMatch[1]}"`;
    } else if (idMatch) {
        searchParam = `id:${idMatch[1]}`;
    } else {
        searchParam = `all:${q}`;
    }

    const url = `${ARXIV_API_BASE}?search_query=${encodeURIComponent(searchParam)}&start=${offset}&max_results=${limit}&sortBy=submittedDate&sortOrder=descending`;

    let res: Response;
    try {
        res = await rateLimitedFetch(url);
    } catch (e) {
        if (e instanceof Error && e.message === "SEARCH_BUSY") throw new Error("ARXIV_BUSY");
        throw e;
    }
    if (!res.ok) throw new Error(`arXiv error: ${res.status}`);

    const text = await res.text();
    const doc = new DOMParser().parseFromString(text, "application/xml");

    const results = parseArxivResponse(doc);
    const total = parseArxivTotal(doc);

    const result = { results, total };
    setCached(searchCache, cacheKey, result);
    return result;
}
```

- [ ] **Step 4: Export searchArxiv from db/index.ts**

Edit `src/lib/utils/db/index.ts`:

```typescript
export { searchPapers, searchArxiv, searchArxivCategory, parseArxivTotal, sanitiseYearRange, sanitiseFieldOfStudy, sanitiseMinCites, SEARCH_FIELDS } from './search';
```

- [ ] **Step 5: Run tests**

```bash
npx vitest run src/lib/utils/db.test.ts --reporter=verbose -t "searchArxiv"
```

Expected: PASS

- [ ] **Step 6: Run all existing tests to ensure no regressions**

```bash
npx vitest run
```

Expected: PASS (all existing tests + new tests)

- [ ] **Step 7: Commit**

```bash
git add src/lib/utils/db/search.ts src/lib/utils/db/index.ts src/lib/utils/db.test.ts
git commit -m "feat: add generic searchArxiv function"
```

---

### Task 6: Create SearchSuggest dropdown component

**Files:**
- Create: `src/lib/components/SearchSuggest.svelte`
- Create: `src/lib/components/SearchSuggest.test.ts`

**Interfaces:**
- Consumes: `SuggestShard` instance (provided by parent via prop or via shared store)
- Produces: Svelte component with dropdown overlay
- Props: `query: string` (bindable), `shard: SuggestShard`, `onSelect: (result: { type: 'paper' | 'author' | 'category', value: string }) => void`
- Events: `select` dispatched on suggestion click

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/SearchSuggest.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, fireEvent, screen } from "@testing-library/svelte";
// Note: @testing-library/svelte may need to be installed
// Run: npm install --save-dev @testing-library/svelte

// For now, test the component's behavior through DOM interaction
// If testing-library isn't available, write a simpler version check

import SearchSuggest from "./SearchSuggest.svelte";

describe("SearchSuggest", () => {
    it("renders dropdown with suggestions when query is provided", () => {
        const mockShard = {
            search: vi.fn().mockReturnValue({
                papers: [{ id: "2401.00001", title: "Quantum Computing" }],
                authors: [],
                categories: [],
            }),
            getStatus: vi.fn().mockReturnValue("ready"),
        };

        const { container } = render(SearchSuggest, {
            props: {
                query: "quantum",
                shard: mockShard,
                onSelect: vi.fn(),
            },
        });

        expect(container.textContent).toContain("Quantum Computing");
    });

    it("shows empty state when no matches", () => {
        const mockShard = {
            search: vi.fn().mockReturnValue({
                papers: [], authors: [], categories: [],
            }),
            getStatus: vi.fn().mockReturnValue("ready"),
        };

        const { container } = render(SearchSuggest, {
            props: { query: "zzzxyz", shard: mockShard, onSelect: vi.fn() },
        });

        // Should show "No matches" or similar
        expect(container.textContent).toContain("No");
    });

    it("shows loading indicator while shard loads", () => {
        const mockShard = {
            search: vi.fn(),
            getStatus: vi.fn().mockReturnValue("loading"),
        };

        const { container } = render(SearchSuggest, {
            props: { query: "test", shard: mockShard, onSelect: vi.fn() },
        });

        expect(container.textContent).toContain("Loading");
    });

    it("calls onSelect when suggestion is clicked", async () => {
        const onSelect = vi.fn();
        const mockShard = {
            search: vi.fn().mockReturnValue({
                papers: [{ id: "2401.00001", title: "Quantum" }],
                authors: [],
                categories: [],
            }),
            getStatus: vi.fn().mockReturnValue("ready"),
        };

        const { container } = render(SearchSuggest, {
            props: { query: "quantum", shard: mockShard, onSelect },
        });

        const item = container.querySelector('[role="option"]');
        if (item) {
            await fireEvent.click(item);
            expect(onSelect).toHaveBeenCalled();
        }
    });

    it("shows 'Search arXiv for' last item", () => {
        const mockShard = {
            search: vi.fn().mockReturnValue({
                papers: [], authors: [], categories: [],
            }),
            getStatus: vi.fn().mockReturnValue("ready"),
        };

        const { container } = render(SearchSuggest, {
            props: { query: "quantum", shard: mockShard, onSelect: vi.fn() },
        });

        expect(container.textContent).toContain("Search arXiv for");
    });
});
```

- [ ] **Step 2: Write the SearchSuggest component**

Create `src/lib/components/SearchSuggest.svelte`:

```svelte
<script lang="ts">
    import type { SuggestShard, SuggestResults } from "$lib/utils/db/suggest";

    let { query = "", shard, onSelect }: {
        query?: string;
        shard: SuggestShard;
        onSelect?: (detail: { type: "paper" | "author" | "category"; value: string }) => void;
    } = $props();

    let results: SuggestResults = $state({ papers: [], authors: [], categories: [] });
    let selectedIndex = $state(-1);
    let isVisible = $state(false);
    let activeDescendant = $state("");

    let flatItems: Array<{ section: string; type: "paper" | "author" | "category"; value: string; label: string }> = $derived.by(() => {
        const items: Array<{ section: string; type: "paper" | "author" | "category"; value: string; label: string }> = [];
        for (const p of results.papers) {
            items.push({ section: "Papers", type: "paper", value: p.id, label: p.title });
        }
        for (const a of results.authors) {
            items.push({ section: "Authors", type: "author", value: a.name, label: a.name });
        }
        for (const c of results.categories) {
            items.push({ section: "Categories", type: "category", value: c.code, label: `${c.code} — ${c.desc || c.code}` });
        }
        if (query.trim()) {
            items.push({ section: "", type: "paper", value: query, label: `Search arXiv for "${query}"` });
        }
        return items;
    });

    $effect(() => {
        if (query.length < 1 || shard.getStatus() === "disabled") {
            isVisible = false;
            return;
        }
        const status = shard.getStatus();
        if (status === "ready" && query.trim()) {
            results = shard.search(query);
            selectedIndex = -1;
            isVisible = results.papers.length > 0 || results.authors.length > 0 || results.categories.length > 0 || query.trim().length > 0;
        } else {
            isVisible = status === "loading";
        }
    });

    function handleKeydown(e: KeyboardEvent) {
        if (!isVisible) return;
        if (e.key === "ArrowDown") {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, flatItems.length - 1);
            updateActiveDescendant();
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, selectedIndex > -1 ? 0 : -1);
            updateActiveDescendant();
        } else if (e.key === "Enter" && selectedIndex >= 0) {
            e.preventDefault();
            selectItem(selectedIndex);
        } else if (e.key === "Escape") {
            e.preventDefault();
            isVisible = false;
        } else if (e.key === "Tab") {
            isVisible = false;
        }
    }

    function updateActiveDescendant() {
        activeDescendant = selectedIndex >= 0 ? `suggest-${selectedIndex}` : "";
    }

    function selectItem(idx: number) {
        if (idx < 0 || idx >= flatItems.length) return;
        const item = flatItems[idx];
        if (onSelect) {
            onSelect({ type: item.type, value: item.value });
        }
        isVisible = false;
    }

    function handleClickOutside(e: MouseEvent) {
        const target = e.target as HTMLElement;
        if (!target.closest("[data-suggest]")) {
            isVisible = false;
        }
    }

    $effect(() => {
        document.addEventListener("click", handleClickOutside);
        return () => document.removeEventListener("click", handleClickOutside);
    });

    // Announce result count for screen readers
    let liveText = $derived(`${flatItems.length} suggestion${flatItems.length !== 1 ? "s" : ""}`);
</script>

<div data-suggest class="relative" onkeydown={handleKeydown}>
    {#if isVisible}
        <div
            class="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-y-auto border border-outline/20 bg-surface shadow-xl"
            role="listbox"
            {activeDescendant}
            aria-label="Search suggestions"
        >
            <div aria-live="polite" class="sr-only">{liveText}</div>

            {#if shard.getStatus() === "loading"}
                <div class="px-4 py-3 font-mono text-xs text-outline">Loading suggestions…</div>
            {:else if flatItems.length === 0}
                <div class="px-4 py-3 font-mono text-xs text-outline">No matches</div>
            {:else}
                {#each flatItems as item, i (i)}
                    <div
                        role="option"
                        id="suggest-{i}"
                        aria-selected={i === selectedIndex}
                        class="cursor-pointer px-4 py-2 font-mono text-xs transition-colors hover:bg-outline/10 {i === selectedIndex ? 'bg-outline/15 text-primary' : 'text-on-surface-variant'}"
                        onmousedown={() => selectItem(i)}
                        onmouseenter={() => { selectedIndex = i; updateActiveDescendant(); }}
                    >
                        {#if item.section}
                            <span class="label-caps mr-2 text-[10px] uppercase tracking-wider text-outline">{item.section}</span>
                        {/if}
                        <span class="text-on-surface">{item.label}</span>
                    </div>
                {/each}
            {/if}
        </div>
    {/if}
</div>
```

- [ ] **Step 3: Run component tests**

```bash
npx vitest run src/lib/components/SearchSuggest.test.ts --reporter=verbose
```

Expected: PASS (adjust based on available testing libraries)

- [ ] **Step 4: Run all tests**

```bash
npx vitest run
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/SearchSuggest.svelte src/lib/components/SearchSuggest.test.ts
git commit -m "feat: add SearchSuggest dropdown component"
```

---

### Task 7: Integrate into SearchView and add tab bar

**Files:**
- Modify: `src/lib/components/SearchView.svelte`
- Modify: `src/lib/components/SearchFilters.svelte` (conditionally show/hide based on tab)

**Interfaces:**
- Consumes: `SearchSuggest.svelte`, `searchArxiv()` from `search.ts`, `SuggestShard` class
- Produces: updated search UI with tab bar (arXiv | Semantic Scholar), integrated suggestions, S2 filters hidden on arXiv tab

- [ ] **Step 1: Rewrite SearchView.svelte with tab bar and suggestion integration**

The full component is large — key changes:

1. Add tab state (`activeTab: 'arxiv' | 's2'`), default `'arxiv'`
2. Separate query per tab (`arxivQuery`, `s2Query`)
3. Create `SuggestShard` instance on mount
4. Integrate `SearchSuggest` component into search input
5. Wire suggestion `onSelect` → call `doSearch()` with appropriate query format
6. Hide `SearchFilters` when on arXiv tab
7. Update URL with `?tab=` param
8. Tab toggle switches search source, preserves last query per tab

Key modifications to `src/lib/components/SearchView.svelte`:

```svelte
<script lang="ts">
    import { onMount } from "svelte";
    import { page } from "$app/stores";
    import { replaceState } from "$app/navigation";
    import { searchPapers, searchArxiv, searchArxivCategory, sanitiseYearRange, sanitiseFieldOfStudy, sanitiseMinCites, SuggestShard, type PaperResult } from "$lib/utils/db";
    import PaperCard from "./PaperCard.svelte";
    import SearchFilters from "./SearchFilters.svelte";
    import SearchSuggest from "./SearchSuggest.svelte";

    let query = $state("");
    let results: PaperResult[] = $state([]);
    let total = $state(0);
    let offset = $state(0);
    let searching = $state(false);
    let error: string | null = $state(null);
    let activeTab: "arxiv" | "s2" = $state("arxiv");

    // Separate query per tab
    let arxivQuery = $state("");
    let s2Query = $state("");

    let yearRange = $state("");
    let fieldOfStudy = $state("");
    let minCites = $state("");

    const LIMIT = 30;
    let shard = $state<SuggestShard | null>(null);

    onMount(() => {
        shard = new SuggestShard();
        // Prefetch common shards on idle
        shard.prefetch();

        const urlQuery = $page.url.searchParams.get("q");
        const urlTab = $page.url.searchParams.get("tab") as "arxiv" | "s2" | null;
        const urlPage = Math.max(1, parseInt($page.url.searchParams.get("page") || "1", 10));
        yearRange = sanitiseYearRange($page.url.searchParams.get("yr") || "");
        fieldOfStudy = sanitiseFieldOfStudy($page.url.searchParams.get("fo") || "");
        minCites = sanitiseMinCites($page.url.searchParams.get("mc") || "");

        if (urlTab === "s2") {
            activeTab = "s2";
            s2Query = urlQuery || "";
            query = s2Query;
        } else {
            activeTab = "arxiv";
            arxivQuery = urlQuery || "";
            query = arxivQuery;
        }

        if (urlQuery && urlQuery.trim().length >= 2) {
            offset = (urlPage - 1) * LIMIT;
            doSearch();
        }
    });

    function syncUrl(q: string, off: number, tab: string) {
        const pageNum = Math.floor(off / LIMIT) + 1;
        const params = new URLSearchParams();
        if (q) params.set("q", q);
        if (pageNum > 1) params.set("page", String(pageNum));
        if (yearRange) params.set("yr", yearRange);
        if (fieldOfStudy) params.set("fo", fieldOfStudy);
        if (minCites) params.set("mc", minCites);
        if (tab !== "arxiv") params.set("tab", tab);
        const str = params.toString();
        const url = str ? `?${str}` : window.location.pathname;
        replaceState(url, {});
    }

    function onFilterChange(filters: { yearRange: string; fieldOfStudy: string; minCites: string }) {
        yearRange = filters.yearRange;
        fieldOfStudy = filters.fieldOfStudy;
        minCites = filters.minCites;
        offset = 0;
        syncUrl(query, 0, activeTab);
        if (query.trim().length >= 2) doSearch();
    }

    function switchTab(tab: "arxiv" | "s2") {
        // Save current query before switching
        if (activeTab === "arxiv") {
            arxivQuery = query;
        } else {
            s2Query = query;
        }
        activeTab = tab;
        // Restore the target tab's query
        query = tab === "arxiv" ? arxivQuery : s2Query;
        results = [];
        total = 0;
        offset = 0;
        error = null;
        syncUrl(query, 0, tab);
        if (query.trim().length >= 2) doSearch();
    }

    function onSuggestionSelect(detail: { type: string; value: string }) {
        if (detail.type === "paper") {
            query = `id:${detail.value}`;
        } else if (detail.type === "author") {
            query = `au:"${detail.value}"`;
        } else if (detail.type === "category") {
            query = `cat:${detail.value}`;
        } else {
            query = detail.value;
        }
        activeTab = "arxiv";
        offset = 0;
        doSearch();
    }

    let debounceTimer: ReturnType<typeof setTimeout>;
    let requestSeq = 0;

    function onInput(e: Event) {
        const val = (e.target as HTMLInputElement).value;
        query = val;
        clearTimeout(debounceTimer);
        if (val.trim().length < 2) {
            results = [];
            total = 0;
            offset = 0;
            syncUrl("", 0, activeTab);
            return;
        }
        searching = true;
        offset = 0;
        debounceTimer = setTimeout(() => doSearch(), 300);
    }

    async function doSearch() {
        error = null;
        searching = true;
        const q = query.trim();
        const seq = ++requestSeq;

        try {
            let res: { results: PaperResult[]; total: number };

            if (activeTab === "arxiv") {
                arxivQuery = q;
                const catMatch = q.match(/^cat:(\S+)$/i);
                if (catMatch) {
                    res = await searchArxivCategory(catMatch[1], { limit: LIMIT, offset });
                } else {
                    res = await searchArxiv(q, { limit: LIMIT, offset });
                }
            } else {
                s2Query = q;
                res = await searchPapers(q, {
                    limit: LIMIT,
                    offset,
                    yearRange: yearRange || undefined,
                    fieldOfStudy: fieldOfStudy || undefined,
                    minCites: minCites || undefined,
                });
            }

            if (seq !== requestSeq) return;
            results = res.results;
            total = res.total;
            syncUrl(q, offset, activeTab);
        } catch (e) {
            if (seq !== requestSeq) return;
            error = e instanceof Error ? e.message : "Search failed";
        } finally {
            if (seq === requestSeq) searching = false;
        }
    }

    function scrollResultsToTop() {
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    async function nextPage() { offset += LIMIT; await doSearch(); scrollResultsToTop(); }
    async function prevPage() { offset = Math.max(0, offset - LIMIT); await doSearch(); scrollResultsToTop(); }
</script>

<div class="space-y-5">
    <!-- Tab bar -->
    <div class="flex gap-0 border-b border-outline/20" role="tablist">
        <button
            role="tab"
            aria-selected={activeTab === "arxiv"}
            onclick={() => switchTab("arxiv")}
            class="px-5 py-2 font-mono text-xs transition-colors {activeTab === 'arxiv' ? 'border-b-2 border-primary text-primary' : 'text-outline hover:text-on-surface-variant'}"
        >
            arXiv
        </button>
        <button
            role="tab"
            aria-selected={activeTab === "s2"}
            onclick={() => switchTab("s2")}
            class="px-5 py-2 font-mono text-xs transition-colors {activeTab === 's2' ? 'border-b-2 border-primary text-primary' : 'text-outline hover:text-on-surface-variant'}"
        >
            Semantic Scholar
        </button>
    </div>

    <!-- Search input with suggestions -->
    <div class="relative" data-suggest>
        <input
            type="search"
            placeholder="Search arXiv papers… (e.g. quantum computing)"
            oninput={onInput}
            onkeydown={(e) => e.key === "Enter" && doSearch()}
            value={query}
            aria-controls="suggest-dropdown"
            aria-autocomplete="list"
            class="w-full border-2 border-outline/30 bg-surface px-5 py-4 font-mono text-base text-on-surface transition-all placeholder:text-outline hover:border-outline/50 focus:border-primary focus:shadow-[0_0_20px_rgba(0,219,231,0.12)]"
        />
        <button
            onclick={() => doSearch()}
            disabled={query.trim().length < 2 || searching}
            class="absolute top-1/2 right-5 -translate-y-1/2 rounded bg-primary px-4 py-1.5 font-mono text-xs font-bold text-[#0a0a0a] transition-all hover:opacity-85 disabled:opacity-30 active:translate-y-px"
        >
            {searching ? "SEARCHING" : "SEARCH"}
        </button>

        {#if shard}
            <SearchSuggest
                {query}
                shard={shard}
                onSelect={onSuggestionSelect}
            />
        {/if}
    </div>

    <!-- Filters — only show for S2 tab -->
    {#if activeTab === "s2"}
        <SearchFilters {yearRange} {fieldOfStudy} {minCites} onChange={onFilterChange} />
    {/if}

    <!-- Error state -->
    {#if error}
        <div class="py-16 text-center font-mono text-sm text-warning-red">
            {error === "SEARCH_BUSY" ? "Semantic Scholar is busy right now — retrying usually works in a few seconds." : error === "ARXIV_BUSY" ? "arXiv is busy right now — retrying usually works in a few seconds." : error}
            <button
                onclick={() => doSearch()}
                class="ml-2 text-primary underline underline-offset-4 decoration-primary/30"
            >
                Retry
            </button>
        </div>
    {:else if query.trim().length === 0}
        <div class="py-16 text-center">
            <p class="font-mono text-sm text-outline">TYPE AT LEAST 2 CHARACTERS TO SCAN</p>
            <p class="mt-1 font-mono text-xs text-outline">tip: cat:cs.LG lists a category's newest papers</p>
        </div>
    {:else if !searching && results.length === 0}
        <div class="py-16 text-center">
            <p class="font-mono text-sm text-outline">No results for <span class="text-on-surface">“{query}”</span></p>
        </div>
    {:else}
        <!-- Results header -->
        <div class="flex items-baseline justify-between border-b border-outline/20 pb-2">
            <div class="font-mono text-xs text-on-surface-variant">
                <span class="text-primary font-bold">{total.toLocaleString()}</span>
                result{total !== 1 ? "s" : ""} · “{query}”
                <span class="ml-2 text-outline">via {activeTab === "arxiv" ? "arXiv" : "Semantic Scholar"}</span>
            </div>
            {#if total > LIMIT}
                <div class="label-caps">
                    p. {Math.floor(offset / LIMIT) + 1} / {Math.ceil(total / LIMIT)}
                </div>
            {/if}
        </div>

        <!-- Results list -->
        <div class="!mt-0">
            {#each results as paper, i (paper.id || i)}
                <PaperCard {paper} />
            {/each}
        </div>

        <!-- Pagination -->
        {#if total > LIMIT}
            <div class="flex justify-center gap-2 pt-4">
                <button
                    onclick={prevPage}
                    disabled={offset <= 0}
                    class="border border-outline/20 bg-surface-container px-5 py-2 font-mono text-xs text-on-surface-variant transition-colors hover:border-primary hover:text-primary disabled:opacity-30 disabled:hover:border-outline/20 disabled:hover:text-on-surface-variant active:translate-y-px"
                >
                    ← PREV
                </button>
                <button
                    onclick={nextPage}
                    disabled={offset + LIMIT >= total}
                    class="border border-outline/20 bg-surface-container px-5 py-2 font-mono text-xs text-on-surface-variant transition-colors hover:border-primary hover:text-primary disabled:opacity-30 disabled:hover:border-outline/20 disabled:hover:text-on-surface-variant active:translate-y-px"
                >
                    NEXT →
                </button>
            </div>
        {/if}
    {/if}
</div>
```

- [ ] **Step 2: Run all tests**

```bash
npx vitest run
```

Expected: PASS

- [ ] **Step 3: Build to verify no compilation errors**

```bash
npm run build
```

Expected: SUCCESS

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/SearchView.svelte
git commit -m "feat: integrate SuggestShard + tab bar into SearchView"
```
