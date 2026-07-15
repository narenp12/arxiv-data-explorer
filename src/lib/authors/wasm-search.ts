import init, { init as wasmInit, search as wasmSearch, search_stats as wasmSearchStats } from "../../../static/wasm/arxwasm/arxwasm.js";

let ready = false;
let initError: string | null = null;

function isReady(): boolean {
  return ready;
}

export async function loadAuthorSearch(): Promise<void> {
  if (ready) return;
  try {
    await init();

    const shardUrls = Array.from({ length: 31 }, (_, i) => `/data/authors/shard-${i}.json`);
    const rankingsUrl = "/data/author_rankings.json";

    const shardTexts = await Promise.all(
      shardUrls.map((url) => fetch(url).then((r) => r.text()))
    );
    const rankingsText = await fetch(rankingsUrl).then((r) => r.text());

    const combined = shardTexts.join("\n");
    wasmInit(combined, rankingsText);
    ready = true;
  } catch (e) {
    initError = String(e);
    throw e;
  }
}

export function getInitError(): string | null {
  return initError;
}

export function searchAuthors(query: string, max = 20): { name: string; weight: number; coauthors: number; rank: number | null }[] {
  if (!ready) return [];
  return wasmSearch(query, max) as { name: string; weight: number; coauthors: number; rank: number | null }[];
}

export function getStats(): { totalAuthors: number; withRankings: number } {
  if (!ready) return { totalAuthors: 0, withRankings: 0 };
  const raw = wasmSearchStats() as { total_authors: number; with_rankings: number };
  return { totalAuthors: raw.total_authors, withRankings: raw.with_rankings };
}
