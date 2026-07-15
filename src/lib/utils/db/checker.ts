type WasmAPI = { default: () => Promise<void>; validate_paper_result_json: (json: string) => string[]; validate_paper_detail_json: (json: string) => string[]; validate_profile_json: (json: string) => string[] };

let _check: WasmAPI | null = null;
let _checkReady = false;

export function ensureChecker(): WasmAPI | null {
	if (!_checkReady) return null;
	return _check;
}

if (import.meta.env.DEV) {
	import("../../../../static/wasm/arxcheck/arxcheck.js")
		.then((m) => m.default().then(() => { _check = m as unknown as WasmAPI; _checkReady = true; }))
		.catch(() => {} /* wasm not present in prod */);
}

export type { WasmAPI };
