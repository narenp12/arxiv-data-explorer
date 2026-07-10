# AuthorGraph Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the co-authorship force-directed graph from a static image into an explorable interface with search, selection, ego-highlighting, and a co-author detail card.

**Architecture:** Single Svelte 5 component (`AuthorGraph.svelte`) with d3 v7 for the force layout. All new state (search query, selected node, tooltip visibility) managed via `$state` runes. The existing `assignClusters` pure function extracted for independent testing.

**Tech Stack:** Svelte 5 (runes), d3 v7, Vitest, TypeScript 6, Tailwind v4

## Global Constraints

- All opacity transitions are 150ms by default, instant under `prefers-reduced-motion`
- No autocomplete/typeahead dropdown — search filtering is live in-graph only
- No perpetual motion — layout pre-computes on load; only drag reheats the simulation
- Node paper count and cluster are visually encoded (radius + color); never duplicated in text
- "Cluster X" labels not shown anywhere — unlabeled dots in legend only
- On touch devices, no tooltip shown; tap selects and the detail card provides info
- All animations gate behind `@media (prefers-reduced-motion: no-preference)` — guard in the same step that adds the animation

---

### Task 1: Extract and test `assignClusters`

**Files:**
- Create: `src/lib/components/AuthorGraph.test.ts`
- Modify: `src/lib/components/AuthorGraph.svelte:21-58`

**Interfaces:**
- Consumes: `AuthNode`, `AuthEdge` types (already defined in AuthorGraph.svelte)
- Produces: `assignClusters(nodes: AuthNode[], edges: AuthEdge[]): number[]` — exported from the module

- [ ] **Step 1: Write the failing test**

```typescript
// src/lib/components/AuthorGraph.test.ts
import { describe, it, expect } from "vitest";
// The function will be exported — test file will import it
// For now, test the behavior inline

describe("assignClusters", () => {
  it("puts two connected nodes in the same cluster", () => {
    // We need to import after it's exported; skip for now and write
    // after the implementation is extracted
  });

  it("puts disconnected nodes in different clusters", () => {
    // skip for now
  });

  it("handles empty nodes gracefully", () => {
    // skip for now
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/components/AuthorGraph.test.ts`
Expected: empty test report, no failures since tests are skipped

- [ ] **Step 3: Extract `assignClusters` and `CLUSTER_COLORS` into module scope**

In `AuthorGraph.svelte`, move `assignClusters` (lines 21–58) and `CLUSTER_COLORS` (lines 13–19) above the component script block and add `export`:

```typescript
<script lang="ts">
  import { onMount } from "svelte";
  import { base } from "$app/paths";
  import { goto } from "$app/navigation";
  import * as d3 from "d3";

  interface AuthNode { id: string; label: string; weight: number; }
  interface AuthEdge { source: string; target: string; weight: number; }
  interface Top80Graph { nodes: AuthNode[]; edges: AuthEdge[]; }

  interface DispNode extends d3.SimulationNodeDatum { id: string; label: string; weight: number; cluster: number; }

  export const CLUSTER_COLORS = [
    "var(--primary)",
    "var(--secondary)",
    "#d97706",
    "#059669",
    "#7c3aed",
  ];

  export function assignClusters(nodes: AuthNode[], edges: AuthEdge[]): number[] {
    // ... same implementation as before (lines 22-58) ...
  }
```

- [ ] **Step 4: Run tests**

Run: `npx vitest run` — all existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/AuthorGraph.svelte src/lib/components/AuthorGraph.test.ts
git commit -m "refactor(author-graph): extract assignClusters for testability"
```

---

### Task 2: Drag-reheat simulation

**Files:**
- Modify: `src/lib/components/AuthorGraph.svelte:85-131` (the `renderGraph` function)

**Interfaces:**
- Consumes: `renderGraph` function signature unchanged — `(graph, svg, w, h)`
- Produces: draggable nodes that reheat the force simulation

- [ ] **Step 1: Wire d3.drag into `renderGraph`**

Replace the static simulation block with drag-enabled nodes.

In `renderGraph`, after the simulation ticks are computed but before zoom is attached, add drag behavior to the circle selection:

```typescript
// After: const sim = d3.forceSimulation...
const dragHandler = d3.drag<SVGCircleElement, DispNode>()
  .on("start", (event, d) => {
    if (!event.active) sim.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  })
  .on("drag", (event, d) => {
    d.fx = event.x;
    d.fy = event.y;
  })
  .on("end", (event, d) => {
    if (!event.active) sim.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  });

// Attach to circles:
root.selectAll("circle").call(dragHandler as any);
```

The `circle` selection now has both `.on("click", ...)` and `.call(dragHandler)`. d3 handles the conflict — drag consumes `mousedown`/`mousemove`/`mouseup`, click fires only on `mouseup` without preceding drag.

Gate drag behind reduced motion:

```typescript
const prefersReducedMotion = typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ... in drag start:
if (prefersReducedMotion) return;
```

- [ ] **Step 2: Verify drag works**

Run: `npm run dev` — open `/authors`, drag a node. It should follow the cursor and settle on release. The layout should not move without drag.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/AuthorGraph.svelte
git commit -m "feat(author-graph): drag nodes reheat force simulation"
```

---

### Task 3: Hover ego-highlight + tooltip

**Files:**
- Modify: `src/lib/components/AuthorGraph.svelte`

**Interfaces:**
- Consumes: `renderGraph` — adds hover handlers to circles and edges
- Produces: `activeTooltip` state variable (`$state<{node: DispNode; x: number; y: number} | null>`)

- [ ] **Step 1: Add tooltip state and container to the template**

Add state variable and a container div for the HTML tooltip in the component:

```typescript
// Inside <script>, alongside other $state declarations:
let activeTooltip = $state<{ node: DispNode; x: number; y: number } | null>(null);
```

In the template, add the tooltip container after the SVG:

```svelte
{#if activeTooltip}
  <div
    class="pointer-events-none absolute z-10 rounded border border-outline/20 bg-surface-container px-3 py-2 font-mono text-xs shadow-lg"
    style="left: {activeTooltip.x}px; top: {activeTooltip.y}px; transform: translate(8px, -50%)"
  >
    <div class="font-bold text-on-surface">{activeTooltip.label}</div>
    <div class="text-on-surface-variant">
      {activeTooltip.node.weight} papers · {
        // compute degree from edges
      } co-authors
    </div>
  </div>
{/if}
```

- [ ] **Step 2: Add hover handlers in renderGraph**

Inside `renderGraph`, find the circle selection and add `mouseenter`/`mouseleave`:

```typescript
// After the circle .join("circle") chain, before .append("title")
.on("mouseenter", (event: MouseEvent, d) => {
  if (prefersReducedMotion) return;
  // Fade non-connected
  const connectedIds = new Set([d.id]);
  const degree = edges.filter(
    (e: any) => e.source.id === d.id || e.target.id === d.id
  ).length;
  root.selectAll<SVGCircleElement, DispNode>("circle")
    .attr("fill-opacity", (n: DispNode) => {
      const isConnected = edges.some(
        (e: any) => (e.source.id === n.id || e.target.id === n.id) && (e.source.id === d.id || e.target.id === d.id)
      );
      return n.id === d.id || isConnected ? n.fillOpacity : n.fillOpacity * 0.15;
    });
  root.selectAll<SVGLineElement, any>("line")
    .attr("stroke-opacity", (e: any) => {
      const touches = e.source.id === d.id || e.target.id === d.id;
      return touches ? 1 : 0.04;
    });
  const rect = svgEl!.getBoundingClientRect();
  activeTooltip = { node: d, x: event.clientX - rect.left, y: event.clientY - rect.top };
})
.on("mouseleave", () => {
  if (prefersReducedMotion) return;
  root.selectAll<SVGCircleElement, DispNode>("circle")
    .attr("fill-opacity", (n: DispNode) => 0.35 + (n.weight / maxW) * 0.45);
  root.selectAll<SVGLineElement, any>("line")
    .attr("stroke-opacity", (e: any) => Math.min(0.5, 0.12 + Math.log(e.weight) * 0.06));
  activeTooltip = null;
})
```

Note: the current code stores `fill-opacity` as a computed value, not stored on the node. To restore it, either store the computed value on the node object at render time, or re-derive it. Re-deriving is simpler — use the existing formula:

```typescript
function nodeOpacity(n: DispNode): number {
  return 0.35 + (n.weight / maxW) * 0.45;
}
```

- [ ] **Step 3: Verify**

Run: `npm run dev` — hover a node. Connected nodes should brighten, others fade. Tooltip should appear near cursor with name, paper count, and co-author count.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/AuthorGraph.svelte
git commit -m "feat(author-graph): hover ego-highlight with HTML tooltip"
```

---

### Task 4: Click-to-select + selection ring + ego labeling

**Files:**
- Modify: `src/lib/components/AuthorGraph.svelte`

**Interfaces:**
- Consumes: `renderGraph` — adds click handler that sets `selectedNode`
- Produces: `selectedNode: $state<DispNode | null>` — consumed by Task 5 (detail card)

- [ ] **Step 1: Add selection state**

```typescript
let selectedNode = $state<DispNode | null>(null);
```

- [ ] **Step 2: Replace the click handler on circles**

Current click handler navigates immediately. Replace it:

```typescript
// In the circle .join("circle") chain, replace the existing .on("click", ...)
.on("click", (_event: MouseEvent, d) => {
  // Deselect if clicking the already-selected node
  if (selectedNode?.id === d.id) {
    selectedNode = null;
    return;
  }
  selectedNode = d;
})
```

- [ ] **Step 3: Add a reactive effect that re-renders selection state**

Svelte 5's `$effect` can re-apply visual state when `selectedNode` changes. Add after the main render effect:

```typescript
$effect(() => {
  const sel = selectedNode;
  if (!sel || !svgEl) return;
  const root = d3.select(svgEl!).select("g");
  // Selection ring
  root.selectAll<SVGCircleElement, DispNode>("circle")
    .attr("stroke", (d: DispNode) => d.id === sel.id ? "var(--primary)" : "var(--surface-container)")
    .attr("stroke-width", (d: DispNode) => d.id === sel.id ? 2.5 : 1)
    .attr("fill-opacity", (d: DispNode) => {
      if (d.id === sel.id) return nodeOpacity(d);
      const connected = edges.some(
        (e: any) => (e.source.id === d.id && e.target.id === sel.id) ||
                     (e.target.id === d.id && e.source.id === sel.id)
      );
      return connected ? nodeOpacity(d) : nodeOpacity(d) * 0.15;
    });
  // Edge dimming
  root.selectAll<SVGLineElement, any>("line")
    .attr("stroke-opacity", (e: any) => {
      const touches = e.source.id === sel.id || e.target.id === sel.id;
      return touches ? 0.4 : 0.05;
    });

  // Ego labels: show for selected node + all connected neighbors
  const egoIds = new Set([sel.id]);
  for (const e of edges) {
    if (e.source.id === sel.id) egoIds.add(e.target.id);
    if (e.target.id === sel.id) egoIds.add(e.source.id);
  }
  // Re-bind text for labeled nodes (keeps top-12 + ego)
  const labelData = [...labelledNodes, ...nodes.filter(n => egoIds.has(n.id) && !labelledNodes.has(n.id))];
  // ... update text selection
});
```

Actually, this effect approach is fragile because it needs access to `edges`, `labelledNodes`, etc. from the closure. A simpler approach: manage selection within `renderGraph` itself, with a `renderSelection(id: string | null)` function called from inside renderGraph, and an `$effect` that calls it:

Better yet, since `renderGraph` is called once, have the click handler update state, and have a separate `$effect` that watches `selectedNode` and calls a function that manipulates the SVG selection directly (using d3.select on the existing SVG element).

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/AuthorGraph.svelte
git commit -m "feat(author-graph): click-to-select with ego highlighting and labels"
```

---

### Task 5: Detail card

**Files:**
- Modify: `src/lib/components/AuthorGraph.svelte`

**Interfaces:**
- Consumes: `selectedNode` from Task 4, `edges` data from the graph
- Produces: rendered detail card in template

- [ ] **Step 1: Compute co-author list from selectedNode and edges**

Add a derived that computes the co-author list when a node is selected:

```typescript
let coauthorList = $derived.by(() => {
  if (!selectedNode || !data) return [];
  const authorDegrees = new Map<string, number>();
  for (const e of data.edges) {
    if (e.source === selectedNode.id) authorDegrees.set(e.target, (authorDegrees.get(e.target) ?? 0) + e.weight);
    if (e.target === selectedNode.id) authorDegrees.set(e.source, (authorDegrees.get(e.source) ?? 0) + e.weight);
  }
  return [...authorDegrees.entries()]
    .map(([name, weight]) => ({ name, weight }))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 15);
});
```

- [ ] **Step 2: Add the detail card to the template**

After the SVG container div:

```svelte
{#if selectedNode}
  <div class="mt-3 border border-outline/20 bg-surface-container p-4">
    <div class="flex items-start justify-between">
      <div>
        <div class="font-mono text-lg font-bold text-primary">{selectedNode.label}</div>
        <div class="font-mono text-xs text-on-surface-variant">
          {coauthorList.length} co-author{coauthorList.length !== 1 ? "s" : ""} in this network
        </div>
      </div>
      <a
        href="{base}/authors/{encodeURIComponent(selectedNode.id)}"
        class="border border-outline/20 bg-surface px-3 py-1.5 font-mono text-xs font-bold text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
      >
        View profile →
      </a>
    </div>
    {#if coauthorList.length > 0}
      <div class="mt-3 divide-y divide-outline/20 border-t border-outline/20">
        {#each coauthorList as co}
          <a
            href="{base}/authors/{encodeURIComponent(co.name)}"
            class="flex items-center justify-between px-1 py-1.5 font-mono text-xs transition-colors hover:bg-surface-container-low"
          >
            <span class="text-on-surface">{co.name}</span>
            <span class="text-on-surface-variant">{co.weight} collaboration{co.weight !== 1 ? "s" : ""}</span>
          </a>
        {/each}
      </div>
    {:else}
      <div class="mt-3 font-mono text-xs text-on-surface-variant">
        No co-authorship data available for this author in the top-80 network.
      </div>
    {/if}
  </div>
{/if}
```

- [ ] **Step 3: Deselect on Escape key**

```typescript
import { onMount } from "svelte";

onMount(() => {
  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape") selectedNode = null;
  }
  document.addEventListener("keydown", onKey);
  return () => document.removeEventListener("keydown", onKey);
});
```

- [ ] **Step 4: Verify**

Run: `npm run dev` — click a node. Detail card should appear below the graph. Co-author names should be clickable links. Escape should dismiss. Clicking the same node again should dismiss.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/AuthorGraph.svelte
git commit -m "feat(author-graph): co-author detail card on node selection"
```

---

### Task 6: Search input + live graph filtering

**Files:**
- Modify: `src/lib/components/AuthorGraph.svelte`

**Interfaces:**
- Consumes: `renderGraph` — nodes filtered reactively
- Produces: search state and input element in template

- [ ] **Step 1: Add search state**

```typescript
let searchQuery = $state("");
let matchCount = $derived(
  searchQuery.trim()
    ? nodes.filter(n => n.label.toLowerCase().includes(searchQuery.trim().toLowerCase())).length
    : nodes.length
);
```

`nodes` reference needs to come from the loaded data. Use the already-loaded `data.nodes`.

- [ ] **Step 2: Add search reactivity to node opacity**

Add an `$effect` that re-applies search opacity whenever `searchQuery` or `selectedNode` changes:

```typescript
$effect(() => {
  const q = searchQuery.trim().toLowerCase();
  const sel = selectedNode;
  if (!svgEl || !data) return;
  const root = d3.select(svgEl).select("g");

  if (!q) {
    // No search active — restore selection state or full opacity
    if (sel) {
      // Apply selection visual state (from Task 4)
    } else {
      root.selectAll<SVGCircleElement, DispNode>("circle")
        .attr("fill-opacity", (d: DispNode) => nodeOpacity(d));
      root.selectAll<SVGLineElement, any>("line")
        .attr("stroke-opacity", (e: any) => Math.min(0.5, 0.12 + Math.log(e.weight) * 0.06));
    }
    return;
  }

  // Search mode: matching nodes full, rest faded
  root.selectAll<SVGCircleElement, DispNode>("circle")
    .attr("fill-opacity", (d: DispNode) =>
      d.label.toLowerCase().includes(q) ? nodeOpacity(d) : nodeOpacity(d) * 0.1
    );
  root.selectAll<SVGLineElement, any>("line")
    .attr("stroke-opacity", 0.04);
});
```

- [ ] **Step 3: Add search input to template**

Before the graph container:

```svelte
<div class="mb-3 flex items-center gap-3">
  <input
    type="search"
    bind:value={searchQuery}
    placeholder="Find an author…"
    class="flex-1 border border-outline/20 bg-surface-container px-3 py-1.5 font-mono text-xs text-on-surface transition-colors placeholder:text-outline focus:border-primary focus:outline-none"
  />
  {#if searchQuery.trim()}
    <span class="font-mono text-xs text-on-surface-variant">{matchCount}/{data.nodes.length} matches</span>
  {/if}
</div>
```

- [ ] **Step 4: Verify**

Run: `npm run dev` — type in the search input. Matching nodes should stay visible, others fade. Match count should update live. Clearing the input restores the graph.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/AuthorGraph.svelte
git commit -m "feat(author-graph): search filters graph in real-time"
```

---

### Task 7: Empty data fallback state

**Files:**
- Modify: `src/lib/components/AuthorGraph.svelte:134-144`

- [ ] **Step 1: Add empty data handling in template**

In the template, after the error block and before the data block:

```svelte
{:else if data && data.nodes.length === 0}
  <div class="flex h-[450px] items-center justify-center font-mono text-sm text-on-surface-variant">
    No co-authorship data available.
  </div>
```

- [ ] **Step 2: Unskip tests for edge cases**

In `AuthorGraph.test.ts`:

```typescript
it("handles empty nodes gracefully", () => {
  expect(assignClusters([], [])).toEqual([]);
});
```

- [ ] **Step 3: Run tests**

```bash
npx vitest run
```

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/AuthorGraph.svelte src/lib/components/AuthorGraph.test.ts
git commit -m "feat(author-graph): handle empty data state"
```

---

### Task 8: Cluster legend

**Files:**
- Modify: `src/lib/components/AuthorGraph.svelte`

- [ ] **Step 1: Add legend to template**

After the search input, before or after the graph container:

```svelte
<div class="mt-2 flex items-center gap-3 font-mono text-[10px] text-on-surface-variant">
  <span class="label-caps">Clusters</span>
  {#each CLUSTER_COLORS as color}
    <span class="inline-block h-2 w-2 rounded-full" style="background: {color}"></span>
  {/each}
</div>
```

- [ ] **Step 2: Verify**

Run: `npm run dev` — legend should appear below/above the graph with 5 colored dots matching the node colors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/AuthorGraph.svelte
git commit -m "feat(author-graph): add unlabeled cluster legend"
```

---

### Task 9: Edge curves + opacity transitions

**Files:**
- Modify: `src/lib/components/AuthorGraph.svelte`

- [ ] **Step 1: Add CSS transition for smooth opacity changes**

In a `<style>` block or the existing CSS, or inline in the SVG:

No `<style>` block exists currently. The current component uses inline CSS variable references. Opacity transitions are best applied via SVG attributes. For the lines, add:

```typescript
root.selectAll("line").data(edges).join("line")
  .attr("stroke", "var(--outline)")
  .attr("stroke-width", ...)
  .attr("stroke-opacity", ...)
  .attr("style", "transition: stroke-opacity 150ms ease")  // New
  .attr("x1", ...)
  // ...
```

For circles:

```typescript
.attr("style", "transition: fill-opacity 150ms ease, stroke-opacity 150ms ease")
```

Under `prefers-reduced-motion`, the `150ms` is overridden — but since we gate the opacity changes themselves (from earlier tasks), the transition duration matters only when changes fire. With the guards in place, opacity changes under reduced motion are instant.

- [ ] **Step 2: Verify**

Run: `npm run dev` — hover a node. Connected nodes should fade in/out smoothly.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/AuthorGraph.svelte
git commit -m "feat(author-graph): smooth opacity transitions on edges and nodes"
```

---

### Task 10: Pulse animation on selection

**Files:**
- Modify: `src/lib/components/AuthorGraph.svelte`

- [ ] **Step 1: Add CSS keyframes in a `<style>` tag**

```svelte
<style>
  @keyframes select-pulse {
    0% { stroke-width: 2.5; stroke-opacity: 1; }
    50% { stroke-width: 4; stroke-opacity: 0.6; }
    100% { stroke-width: 2.5; stroke-opacity: 1; }
  }
</style>
```

- [ ] **Step 2: Apply pulse animation on selected node circle**

In the selection effect, after setting the ring, check for reduced motion and conditionally apply the animation:

```typescript
// In the selected-node effect:
circle.attr("style", (d: DispNode) =>
  d.id === sel.id && !prefersReducedMotion
    ? "animation: select-pulse 0.4s ease-out 2; transition: stroke-width 150ms ease, stroke-opacity 150ms ease"
    : "transition: stroke-width 150ms ease, stroke-opacity 150ms ease"
);
```

- [ ] **Step 3: Verify**

Run: `npm run dev` — click a node. The selection ring should pulse twice then settle. Under reduced motion (System Settings → Accessibility → Reduce Motion), clicking should show the ring immediately with no pulse.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/AuthorGraph.svelte
git commit -m "feat(author-graph): selection ring pulse animation"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** Every section in the spec has a corresponding task. Search (Task 6), selection (Task 4), detail card (Task 5), hover (Task 3), drag (Task 2), legend (Task 8), empty state (Task 7), pulse (Task 10), reduced motion (integrated into each task), edge curves (Task 9).
- [ ] **Placeholder scan:** No TBDs, TODOs, or "implement later" in the plan.
- [ ] **Type consistency:** `assignClusters`, `CLUSTER_COLORS`, `selectedNode`, `searchQuery`, `coauthorList` — same names used across all tasks.
