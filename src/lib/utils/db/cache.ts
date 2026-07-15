export const CACHE_LIMIT = 100;
export const searchCache = new Map<string, unknown>();
export const detailCache = new Map<string, unknown>();

export function getCached<K, V>(cache: Map<K, V>, key: K): V | undefined {
	const val = cache.get(key);
	if (val !== undefined) {
		cache.delete(key);
		cache.set(key, val);
	}
	return val;
}

export function setCached<K, V>(cache: Map<K, V>, key: K, value: V) {
	cache.delete(key);
	cache.set(key, value);
	if (cache.size > CACHE_LIMIT) {
		const oldestKey = cache.keys().next().value as K;
		cache.delete(oldestKey);
	}
}

import { resetRateLimitState } from './rate-limit';

export function clearSearchCache() {
	resetRateLimitState();
	searchCache.clear();
	detailCache.clear();
}
