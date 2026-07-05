import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = resolve(__dirname, "poisson_var.py");

if (!existsSync(script)) {
  console.error("Missing:", script);
  process.exit(1);
}

try {
  console.log("Running Poisson VAR inference…");
  execSync(`python3 "${script}"`, { stdio: "inherit", cwd: resolve(__dirname, "..") });
} catch {
  console.error("Poisson VAR inference failed. Install deps: pip install -r scripts/requirements.txt");
  process.exit(1);
}
