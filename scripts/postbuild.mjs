import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, "..");

// Trend + edge estimation (numpy only). The generated JSON is committed, so a
// missing python/numpy on the build host is a warning, not a failure — the
// checked-in data is used as-is.
const trends = resolve(__dirname, "build_trends.py");
if (existsSync(trends)) {
  try {
    console.log("Rebuilding trend data (build_trends.py)…");
    execSync(`python3 "${trends}"`, { stdio: "inherit", cwd: root });
  } catch {
    console.warn("build_trends.py failed (numpy missing?) — using committed static/data JSON.");
  }
}

// Author graph shards (plain node, no deps) — must succeed.
const shards = resolve(__dirname, "build_author_shards.mjs");
if (existsSync(shards)) {
  console.log("Rebuilding author shards (build_author_shards.mjs)…");
  execSync(`node "${shards}"`, { stdio: "inherit", cwd: root });
}

// The build output copies static/ before postbuild runs, so refresh the data
// directory inside build/ with whatever the scripts just regenerated.
execSync(`cp -R "${resolve(root, "static/data/.")}" "${resolve(root, "build/data/")}"`, { cwd: root });
console.log("postbuild complete.");
