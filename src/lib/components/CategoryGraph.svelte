<script lang="ts">
  import { onMount } from "svelte";
  import { base } from "$app/paths";
  import * as d3 from "d3";

  interface CategoryNode {
    id: string;
    label: string;
    domain: string;
    group: string;
    weight: number;
    color: string;
  }

  interface CategoryEdge {
    source: string;
    target: string;
    weight: number;
  }

  interface CategoryGraphData {
    nodes: CategoryNode[];
    edges: CategoryEdge[];
  }

  let svgEl = $state<SVGSVGElement>();
  let containerEl = $state<HTMLDivElement>();
  let data = $state<CategoryGraphData | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);

  onMount(async () => {
    try {
      const resp = await fetch(`${base}/data/category_graph.json`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      data = await resp.json();
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load graph";
    } finally {
      loading = false;
    }
  });

  $effect(() => {
    if (!data || !svgEl) return;
    const w = svgEl.clientWidth || containerEl?.clientWidth || 800;
    const h = Math.max(400, Math.min(600, w * 0.55));
    renderGraph(data, svgEl, w, h);
  });

  function renderGraph(graph: CategoryGraphData, svg: SVGSVGElement, w: number, h: number) {
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);

    d3.select(svg).selectAll("*").remove();

    const simulation = d3.forceSimulation(graph.nodes)
      .force("link", d3.forceLink(graph.edges).id((d: any) => d.id).distance(60))
      .force("charge", d3.forceManyBody().strength(-120))
      .force("center", d3.forceCenter(w / 2, h / 2))
      .force("collision", d3.forceCollide().radius(8));

    const link = d3.select(svg).append("g")
      .selectAll("line")
      .data(graph.edges)
      .join("line")
      .attr("stroke", "#4a5568")
      .attr("stroke-width", (d) => Math.max(0.5, Math.log(d.weight) / 3))
      .attr("stroke-opacity", 0.3);

    const node = d3.select(svg).append("g")
      .selectAll("circle")
      .data(graph.nodes)
      .join("circle")
      .attr("r", (d) => Math.max(4, Math.sqrt(d.weight) / 15))
      .attr("fill", (d) => d.color)
      .attr("stroke", "#1a1a2e")
      .attr("stroke-width", 1)
      .attr("cursor", "pointer")
      .append("title")
      .text((d) => `${d.label} (${d.weight.toLocaleString()} papers)`);

    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node
        .attr("cx", (d: any) => d.x)
        .attr("cy", (d: any) => d.y);
    });
  }
</script>

<div bind:this={containerEl} class="w-full">
  {#if loading}
    <div class="flex h-[450px] items-center justify-center">
      <div class="animate-pulse text-slate-500 dark:text-slate-400">Loading graph…</div>
    </div>
  {:else if error}
    <div class="flex h-[450px] items-center justify-center text-red-400">
      Failed to load: {error}
      <button onclick={() => location.reload()} class="ml-2 underline hover:text-red-300">Retry</button>
    </div>
  {:else}
    <svg
      bind:this={svgEl}
      class="h-[450px] w-full sm:h-[500px]"
      role="img"
      aria-label="Category co-occurrence network graph showing {data.nodes.length} categories and {data.edges.length} connections"
    ></svg>
  {/if}
</div>
