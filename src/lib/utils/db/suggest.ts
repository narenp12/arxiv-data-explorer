import FlexSearch, { Document as FlexDocument } from "flexsearch";

const SHARD_BASE = "/data/search/suggest";
const LRU_MAX = 3;

interface ShardEntry {
  t: [string, string][];
  a: [string, number][];
}

interface CategoriesEntry {
  c: [string, string][];
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

import { ungzip } from "pako";

async function gunzip(buf: ArrayBuffer): Promise<string> {
  const bytes = ungzip(new Uint8Array(buf));
  return new TextDecoder().decode(bytes);
}

async function loadCategories(): Promise<void> {
  if (categoriesData) return;
  if (categoriesPromise) return categoriesPromise;
  categoriesPromise = (async () => {
    try {
      const res = await fetch(`${SHARD_BASE}/categories.json.gz`);
      if (!res.ok) return;
      const buf = await res.arrayBuffer();
      const text = await gunzip(buf);
      categoriesData = JSON.parse(text);
    } catch {}
  })();
  return categoriesPromise;
}

export class SuggestShard {
  private letter: string = "";
  private index: FlexDocument<{ id: string; title: string }> | null = null;
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

    const needsRefresh = await this.checkVersion();
    if (needsRefresh) {
      this.clearCache();
    }

    if (this.controller) {
      this.controller.abort();
    }
    this.controller = new AbortController();

    try {
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
        raw = await gunzip(buf);
        entry = JSON.parse(raw);
        this.cacheShard(letter, raw);
      }

      if (!entry || !("t" in entry)) throw new Error("Invalid shard format");

      this.papers = entry.t.map(([id, title]) => ({ id, title }));
      this.authors = entry.a.map(([name, rankIndex]) => ({ name, rankIndex }));

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

      loadCategories().catch(() => {});

      this.status = "ready";
    } catch (e: any) {
      if (e?.name === "AbortError") return;
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

    if (this.index) {
      const raw = this.index.search(q, { limit });
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

    for (const a of this.authors) {
      if (results.authors.length >= limit) break;
      if (a.name.toLowerCase().includes(q)) {
        results.authors.push(a);
      }
    }

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
    const letters = ["a", "c", "m", "s", "t"];
    const cb = () => {
      for (const l of letters) {
        if (!sessionStorage.getItem(`suggest_shard_${l}`)) {
          fetch(`${SHARD_BASE}/${l}.json.gz`)
            .then(r => r.arrayBuffer())
            .then(buf => gunzip(buf))
            .then(raw => {
              this.cacheShard(l, raw);
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
        return true;
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
        } catch {}
      }
    }
  }

  private clearCache(): void {
    sessionStorage.clear();
    this.lruKeys = [];
  }
}
