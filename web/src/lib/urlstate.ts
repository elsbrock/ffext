/**
 * Filter state <-> query string.
 *
 * Every filter the UI exposes is representable in the URL so a particular view
 * — "MIT-licensed, no broad host access, score >= 80, sorted by last update" —
 * is a link someone else can open. Only non-default values are written, which
 * keeps the shared URL short and keeps the unfiltered landing page at a bare
 * `/` rather than a query string full of defaults.
 */
import { defaultFilters, type Filters, type SortKey } from './catalog.svelte';

const SORT_KEYS: SortKey[] = ['score', 'users', 'updated', 'rating', 'name'];

const SET_PARAMS = {
	cat: 'categories',
	lic: 'licenseFamilies',
	dc: 'dataCollection'
} as const;

const FLAG_PARAMS = {
	nobroad: 'excludeBroadHost',
	norisk: 'excludeHighRisk',
	maintained: 'maintainedOnly'
} as const;

export function filtersToParams(f: Filters): URLSearchParams {
	const p = new URLSearchParams();
	if (f.query.trim()) p.set('q', f.query.trim());
	if (f.sort !== 'score') p.set('sort', f.sort);
	if (f.includeDeclared) p.set('tier', 'all');
	for (const [param, key] of Object.entries(SET_PARAMS)) {
		const v = f[key];
		if (v.size) p.set(param, [...v].sort().join(','));
	}
	for (const [param, key] of Object.entries(FLAG_PARAMS)) {
		if (f[key]) p.set(param, '1');
	}
	if (f.minScore > 0) p.set('min', String(f.minScore));
	return p;
}

export function filtersFromParams(p: URLSearchParams): Filters {
	const f = defaultFilters();
	f.query = p.get('q') ?? '';

	const sort = p.get('sort');
	if (sort && (SORT_KEYS as string[]).includes(sort)) f.sort = sort as SortKey;

	f.includeDeclared = p.get('tier') === 'all';

	for (const [param, key] of Object.entries(SET_PARAMS)) {
		const raw = p.get(param);
		if (raw) f[key] = new Set(raw.split(',').filter(Boolean));
	}
	for (const [param, key] of Object.entries(FLAG_PARAMS)) {
		if (p.get(param) === '1') f[key] = true;
	}

	// Clamped rather than trusted: minScore drives a slider, and an out-of-range
	// value from a hand-edited URL would leave the control showing nothing.
	const min = Number(p.get('min'));
	if (Number.isFinite(min)) f.minScore = Math.min(100, Math.max(0, Math.round(min)));

	return f;
}

/** The query string for a set of filters, empty when everything is at default. */
export function filtersToQuery(f: Filters): string {
	const p = filtersToParams(f).toString();
	return p ? `?${p}` : '';
}
