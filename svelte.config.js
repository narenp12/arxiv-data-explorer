import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

/** @type {import("@sveltejs/kit").Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: "build",
      assets: "build",
      fallback: "404.html",
      precompress: false,
      strict: true,
    }),
    prerender: {
      handleHttpError: ({ path }) => {
        if (path.startsWith("/trends") || path.startsWith("/takeoffs")) return;
        throw new Error(`${path} returned 404`);
      },
    },
    paths: {
      base: "",
    },
  },
};

export default config;
