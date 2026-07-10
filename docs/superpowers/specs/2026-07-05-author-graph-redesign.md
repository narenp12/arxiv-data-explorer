# Search-First Co-authorship Graph

Redesign of `AuthorGraph.svelte` — the top-80 co-authorship force-directed graph on `/authors`.

**State:** Approved design
**Audit pass:** anti-slop + design-taste applied

---

## 1. Interaction Model

### Default state
Full graph renders with pre-computed layout (current behavior). No animation on load — the graph appears settled. Top 12 nodes by weight are labeled.

### Hover
Hovering any node triggers:
- **Ego highlight** — the hovered node + its direct edges + connected nodes stay at full opacity; everything else fades to 15% over 150ms via CSS transition.
- **Tooltip** — positioned HTML overlay near cursor:
  - Author name (medium weight)
  - Paper count · N co-authors
- Mouseleave restores full opacity over 150ms.
- On touch devices, the tooltip is never shown. Tap selects the node and the detail card provides the same information.

### Click to select (replaces immediate navigation)
Clicking a node **selects** it (does not navigate):
- Selected node gets a `var(--primary)` ring, 2.5px stroke, with a subtle pulse animation (CSS `scale` + `opacity` loop — 2 beats then settles).
- Labels appear on the selected node **and all its immediate neighbors** (the ego network). The static top-12 labels remain; the ego labels are additive.
- A **detail card** slides in below the graph container.
- A second click on the same node, clicking blank SVG space, or pressing `Escape` deselects and hides the card.

### Click → navigate
The only navigation action is the "View profile" link inside the detail card. This is explicit and intentional — clicking the graph itself explores, not navigates away.

### Drag
Nodes are draggable. The simulation reheats on drag (`simulation.alpha(0.3).restart()`) and settles again once released. This is the **only** time the layout animates.

---

## 2. Search Layer

A search input above the graph, secondary to click exploration.

```
┌────────────────────────────────────────────┐
│  Find an author…             3/80 matches  │
└────────────────────────────────────────────┘
```

- Case-insensitive, partial match against `node.label`.
- Matching nodes stay full opacity; non-matching fade to 10% over 150ms.
- Match count shown on the right.
- Empty input restores all nodes.
- No autocomplete dropdown — filtering is live and visible in the graph itself. This avoids the "typeahead steals focus from the visualization" problem.
- Zero matches: all nodes fade to 10%, and the match count shows "0/80" with muted text. The graph remains visible in context.

### States

| State | Graph appearance | Search UI |
|-------|-----------------|-----------|
| Default (empty input) | All nodes full opacity, top-12 labels | Placeholder text, no count |
| Typing, has matches | Matching nodes full, rest faded | Shows "N/80 matches" |
| Typing, zero matches | All nodes faded to 10% | Shows "0/80" |
| Input cleared | Restores default state | Placeholder text, no count |

---

## 3. Detail Card

Appears below the graph container when a node is selected. Shows **only what the graph does not visually encode**.

```
┌──────────────────────────────────────────────────────────┐
│  Yann LeCun                              ┌────────────┐ │
│  12 co-authors in this network           │ View →     │ │
│                                          └────────────┘ │
│  · Léon Bottou         12 collaborations                 │
│  · Yoshua Bengio        8 collaborations                 │
│  · Koray Kavukcuoglu    6 collaborations                 │
│  · Leonid Karlinsky     5 collaborations                 │
│  · … (up to 15)                                          │
└──────────────────────────────────────────────────────────┘
```

- **Name** — large mono, primary color
- **Co-author count** — from edge degree (`connections`), the one number not encoded in the visualization
- **Co-author list** — sorted by edge weight descending, max 15 items. Each row: name + collaboration count.
- **"View profile" link** — navigates to `/authors/{id}`. This is the sole navigation trigger.
- No paper count (already encoded as node radius). No cluster (already encoded as color).

---

## 4. Legend

Bottom-left of the graph container, inline:

```
●  ●  ●  ●  ●
```

One row, 5 dots matching `CLUSTER_COLORS`. No labels — the clusters are internally-derived groupings, not semantic categories. Color alone is sufficient encoding. The tooltip already shows per-node info.

---

## 5. Visual Design (Dial Settings)

| Dial | Value | Rationale |
|------|-------|-----------|
| DESIGN_VARIANCE | 5 | Force layout is organic; don't fight it |
| MOTION_INTENSITY | 4 | Transition opacity only; no bounce, no perpetual drift |
| VISUAL_DENSITY | 6 | 80 nodes + labels is busy; need clear grouping |

### Edge rendering
- Curved paths instead of straight lines when two nodes share multiple edges (unlikely in co-authorship, but the data model supports it).
- Existing log-scaled width and opacity mapping preserved.
- On hover, connected edges go to full opacity; on select, connected edges stay at `0.4` while non-connected drop to `0.05`.

### Reduced motion
All animations gate behind `@media (prefers-reduced-motion: no-preference)`:
- Selection pulse: skipped. Ring appears immediately at `stroke-width: 2.5`, full opacity.
- Hover opacity transitions: instant (0ms) instead of 150ms.
- Search filter transitions: instant instead of 150ms.
- Drag-reheat: disabled. Nodes are not draggable under reduced motion.

### Node rendering
- Radius: `max(2, min(8, sqrt(weight) * 0.15))` (unchanged)
- Fill opacity: `0.35 + (weight / maxWeight) * 0.45` (unchanged)
- Selected ring: `stroke="var(--primary)" stroke-width="2.5"` with a CSS keyframe pulse (2 cycles):
  ```css
  @keyframes select-pulse {
    0% { stroke-width: 2.5; stroke-opacity: 1; }
    50% { stroke-width: 4; stroke-opacity: 0.6; }
    100% { stroke-width: 2.5; stroke-opacity: 1; }
  }
  ```

---

## 6. Data Flow (unchanged)

- `onMount` fetches `${base}/data/authors/top80.json` (same as today)
- `assignClusters` runs once on load (same)
- `renderGraph` called inside `$effect` when data + SVG element are ready
- Search state, selection state, and detail card state managed with `$state` in the component

---

## 7. States Coverage

| State | What renders |
|-------|-------------|
| Loading | Centered "Loading network…" (unchanged) |
| Error | Centered error message (unchanged) |
| Empty data (0 nodes) | `"No co-authorship data available"` (new — currently unhandled) |
| Default | Graph, top-12 labels, cluster legend |
| Searching, has matches | Graph with matching nodes bright, rest faded, match count |
| Searching, no matches | All nodes faded, "0/80" in search input |
| Node hovered | Ego highlight, tooltip visible |
| Node selected | Ring on selected, ego labels, detail card visible |
| Drag active | Layout reheated, nodes follow cursor |
| Zoomed/panned | All interactions preserved (d3.zoom already implemented) |

---

## 8. What Stays the Same

- Data source: `top80.json`
- Cluster algorithm: BFS connected components → degree-ranked buckets
- 5 `CLUSTER_COLORS` mapped to CSS variables
- Zoom/pan via `d3.zoom` with `scaleExtent([0.5, 6])`
- SVG viewBox sizing and responsive height
- Loading and error states

---

## 9. No-Change List (Anti-Slop Constraints)

These were considered and rejected:

- **No typeahead/autocomplete dropdown** — search is live in-graph filtering. A dropdown would compete with the graph for attention and add no information the visual doesn't already show.
- **No perpetual motion** — the layout settles. Only drag reheats it. A bouncing graph is cognitively expensive and teaches nothing.
- **No stats dump in the detail card** — paper count and cluster are dropped from the card because they're already visually encoded. Redundancy is clutter.
- **No click-to-navigate** on the graph itself — clicking selects. Navigation is an explicit action ("View profile"). This prevents accidental navigation during exploration.
- **No labels beyond ego network on selection** — only the selected node and its neighbors get labels. Labeling the full graph on selection would produce text noise.
- **No cluster labels in tooltip or legend** — clusters are internal grouping heuristics, not named categories. Color alone is sufficient.
- **No tooltip on touch devices** — hover doesn't exist on mobile; tap selects, and the detail card provides the same info.

---

## 10. Implementation Order

Each step includes its reduced-motion guard (`@media (prefers-reduced-motion: no-preference)`) so no retrofitting is needed.

1. **Drag-reheat simulation** — keep pre-computed layout on load (current behavior), wire `d3.drag` to call `simulation.alpha(0.3).restart()` on drag start. Gate drag behind reduced-motion check.
2. **Hover ego highlight + tooltip** — opacity transitions on node/edge groups (150ms, instant under reduced motion). HTML tooltip near cursor. No tooltip on touch.
3. **Click-to-select + selection ring + ego labeling** — selection ring appears immediately under reduced motion, no pulse.
4. **Detail card** — co-author list only. Slides in below graph container.
5. **Search input + live graph filtering** — opacity transitions on non-matching nodes (150ms, instant under reduced motion).
6. **Empty data fallback state** — `"No co-authorship data available"` when graph has 0 nodes.
7. **Cluster legend** — unlabeled colored dots, bottom-left of container.
8. **Edge curves + opacity transitions** — curved paths for multi-edges; hover/select opacity mappings.
9. **Pulse animation on selection** — CSS keyframe, 2 cycles, gated behind reduced motion.

Steps 1-4 are the core teaching interaction. Steps 5-9 are refinements. Each step is independently ship-able.
