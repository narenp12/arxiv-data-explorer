import { describe, it, expect, vi, beforeEach } from "vitest";
import { gzip } from "pako";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

let sessionData: Record<string, string> = {};
let localData: Record<string, string> = {};
const mockSessionStorage = {
  getItem: vi.fn((k: string) => sessionData[k] ?? null),
  setItem: vi.fn((k: string, v: string) => { sessionData[k] = v; }),
  removeItem: vi.fn((k: string) => { delete sessionData[k]; }),
  clear: vi.fn(() => { sessionData = {}; }),
};
vi.stubGlobal("sessionStorage", mockSessionStorage);
vi.stubGlobal("localStorage", {
  getItem: vi.fn((k: string) => localData[k] ?? null),
  setItem: vi.fn((k: string, v: string) => { localData[k] = v; }),
  removeItem: vi.fn((k: string) => { delete localData[k]; }),
  clear: vi.fn(() => { localData = {}; }),
});

function metaResponse(): Response {
  return new Response(JSON.stringify({ version: 1 }));
}

function gzipBytes(data: object): Uint8Array {
  return gzip(JSON.stringify(data));
}

function mockGzipResponse(data: object): Response {
  return new Response(gzipBytes(data) as BodyInit, {
    headers: { "content-type": "application/gzip" },
  });
}

describe("SuggestShard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionData = {};
    localData = {};
  });

  it("loads a shard and builds a FlexSearch index", async () => {
    const shardData = {
      t: [["arXiv:2401.00001", "Quantum Computing"], ["arXiv:2401.00002", "Quantum Theory"]],
      a: [["Einstein", 0], ["Feynman", 1]],
    };
    mockFetch.mockImplementation((url: string) => {
      if (url.endsWith("meta.json")) return Promise.resolve(metaResponse());
      if (url.endsWith("categories.json.gz")) return Promise.resolve(mockGzipResponse({ c: [] }));
      return Promise.resolve(mockGzipResponse(shardData));
    });

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
    mockFetch.mockImplementation((url: string) => {
      if (url.endsWith("meta.json")) return Promise.resolve(metaResponse());
      if (url.endsWith("categories.json.gz")) return Promise.resolve(mockGzipResponse({ c: [] }));
      return Promise.resolve(mockGzipResponse(shardData));
    });

    const { SuggestShard } = await import("./suggest.js");
    const ss = new SuggestShard();
    await ss.load("t");

    expect(mockSessionStorage.getItem).toHaveBeenCalled();
    expect(mockSessionStorage.setItem).toHaveBeenCalled();

    const fetchCount1 = mockFetch.mock.calls.length;

    const ss2 = new SuggestShard();
    await ss2.load("t");

    const fetchCount2 = mockFetch.mock.calls.length;
    expect(fetchCount2 - fetchCount1).toBe(1); // only checkVersion
  });

  it("search returns empty results for no match", async () => {
    const shardData = { t: [["arXiv:2401.00001", "Quantum Computing"]], a: [] };
    mockFetch.mockImplementation((url: string) => {
      if (url.endsWith("meta.json")) return Promise.resolve(metaResponse());
      if (url.endsWith("categories.json.gz")) return Promise.resolve(mockGzipResponse({ c: [] }));
      return Promise.resolve(mockGzipResponse(shardData));
    });

    const { SuggestShard } = await import("./suggest.js");
    const ss = new SuggestShard();
    await ss.load("q");
    const results = ss.search("biology");
    expect(results.papers).toHaveLength(0);
    expect(results.authors).toHaveLength(0);
  });

  it("returns empty results when disabled", async () => {
    const { SuggestShard } = await import("./suggest.js");
    const ss = new SuggestShard();
    (ss as any).status = "disabled";
    const results = ss.search("anything");
    expect(results.papers).toHaveLength(0);
    expect(results.authors).toHaveLength(0);
  });
});
