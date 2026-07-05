import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    // Mirrors the Cloudflare Pages Functions in functions/api/ — both APIs
    // must be same-origin because they lack usable CORS headers.
    proxy: {
      "/api/arxiv": {
        target: "https://export.arxiv.org",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/arxiv/, "/api/query"),
      },
      "/api/s2": {
        target: "https://api.semanticscholar.org",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/s2/, ""),
      },
    },
  },
});
