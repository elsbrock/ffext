import { base } from '$app/paths';
import type { ExtensionDetail, IndexItem, Meta } from './types';

export type SortKey = 'score' | 'users' | 'updated' | 'rating' | 'name';

export interface Filters {
	query: string;
	includeDeclared: boolean;
	categories: Set<string>;
	licenseFamilies: Set<string>;
	dataCollection: Set<string>;
	/** Exclude anything requesting access to all websites. */
	excludeBroadHost: boolean;
	/** Exclude anything with any high-risk permission. */
	excludeHighRisk: boolean;
	/** Only extensions updated within the last two years. */
	maintainedOnly: boolean;
	minScore: number;
	sort: SortKey;
}

export function defaultFilters(): Filters {
	return {
		query: '',
		includeDeclared: false,
		categories: new Set(),
		licenseFamilies: new Set(),
		dataCollection: new Set(),
		excludeBroadHost: false,
		excludeHighRisk: false,
		maintainedOnly: false,
		minScore: 0,
		sort: 'score'
	};
}

class Catalog {
	meta = $state.raw<Meta | null>(null);
	// $state.raw, not $state: these arrays are replaced wholesale and never
	// mutated in place, and deep-proxying 71k records would be pure overhead.
	// It also keeps the objects referentially identical to what we indexed below.
	verified = $state.raw<IndexItem[]>([]);
	declared = $state.raw<IndexItem[]>([]);
	loadingDeclared = $state(false);
	ready = $state(false);
	error = $state<string | null>(null);

	/** Lowercased "name + summary" per id, so query filtering never re-lowercases
	 *  71k strings on every keystroke. Keyed by id rather than object identity so
	 *  it stays correct regardless of any proxy wrapping. */
	#haystack = new Map<number, string>();

	async init() {
		if (this.ready) return;
		try {
			const [meta, verified] = await Promise.all([
				fetch(`${base}/data/meta.json`).then((r) => r.json() as Promise<Meta>),
				fetch(`${base}/data/index-verified.json`).then((r) => r.json() as Promise<IndexItem[]>)
			]);
			this.meta = meta;
			this.verified = verified;
			this.#index(verified);
			this.ready = true;
		} catch (e) {
			this.error = e instanceof Error ? e.message : String(e);
		}
	}

	async loadDeclared() {
		if (this.declared.length || this.loadingDeclared) return;
		this.loadingDeclared = true;
		try {
			const d = (await fetch(`${base}/data/index-declared.json`).then((r) =>
				r.json()
			)) as IndexItem[];
			this.#index(d);
			this.declared = d;
		} catch (e) {
			this.error = e instanceof Error ? e.message : String(e);
		} finally {
			this.loadingDeclared = false;
		}
	}

	#index(items: IndexItem[]) {
		for (const it of items) {
			this.#haystack.set(it.id, `${it.n}\n${it.d}`.toLowerCase());
		}
	}

	haystack(it: IndexItem) {
		let h = this.#haystack.get(it.id);
		if (h === undefined) {
			h = `${it.n}\n${it.d}`.toLowerCase();
			this.#haystack.set(it.id, h);
		}
		return h;
	}

	/** Detail records are sharded by id % 256 so one page view fetches ~1/256th. */
	async detail(id: number): Promise<ExtensionDetail | null> {
		const shard = id % 256;
		const cached = this.#shards.get(shard);
		const map = cached ?? (await this.#fetchShard(shard));
		return map[String(id)] ?? null;
	}

	#shards = new Map<number, Record<string, ExtensionDetail>>();

	async #fetchShard(shard: number) {
		const r = await fetch(`${base}/data/ext/${shard}.json`);
		if (!r.ok) throw new Error(`shard ${shard}: ${r.status}`);
		const map = (await r.json()) as Record<string, ExtensionDetail>;
		this.#shards.set(shard, map);
		return map;
	}
}

export const catalog = new Catalog();

const MAINTAINED_DAYS = 730;

/**
 * How many ratings an extension needs before its own average outweighs the
 * corpus average. Sorting on the raw average is close to useless here: the
 * median rated extension in the corpus has two ratings, and 6,373 of them hold
 * a perfect 5.0 off three ratings or fewer, so a raw sort returns a wall of
 * noise and buries the things thousands of people actually rated.
 *
 * 20 is roughly the 90th percentile of rating counts — high enough that a
 * handful of reviews cannot buy the top of the list, low enough that a
 * genuinely well-liked niche extension still surfaces.
 */
const RATING_PRIOR_WEIGHT = 20;

/** Corpus mean rating, computed once per pool. */
const ratingPriors = new WeakMap<IndexItem[], number>();

function ratingPrior(items: IndexItem[]): number {
	const cached = ratingPriors.get(items);
	if (cached !== undefined) return cached;
	let sum = 0;
	let n = 0;
	for (const it of items) {
		if (it.rc > 0 && it.r > 0) {
			sum += it.r;
			n += 1;
		}
	}
	const prior = n ? sum / n : 0;
	ratingPriors.set(items, prior);
	return prior;
}

/**
 * Rating average pulled toward the corpus mean in proportion to how little
 * evidence backs it (a Bayesian/"true Bayesian estimate" shrink). An unrated
 * extension scores 0 rather than the mean, so it sorts below everything that
 * has any evidence at all instead of tying with thousands of other blanks.
 */
export function weightedRating(it: IndexItem, prior: number): number {
	if (!it.rc || !it.r) return 0;
	return (it.r * it.rc + prior * RATING_PRIOR_WEIGHT) / (it.rc + RATING_PRIOR_WEIGHT);
}

export function applyFilters(items: IndexItem[], f: Filters): IndexItem[] {
	const q = f.query.trim().toLowerCase();
	const terms = q ? q.split(/\s+/) : [];
	const hasCat = f.categories.size > 0;
	const hasLic = f.licenseFamilies.size > 0;
	const hasDc = f.dataCollection.size > 0;

	const out: IndexItem[] = [];
	for (const it of items) {
		if (f.minScore && it.sc < f.minScore) continue;
		if (f.excludeBroadHost && it.bh) continue;
		if (f.excludeHighRisk && it.hp > 0) continue;
		if (f.maintainedOnly && (it.ag === null || it.ag > MAINTAINED_DAYS)) continue;
		if (hasLic && !f.licenseFamilies.has(it.lf)) continue;
		if (hasDc && !f.dataCollection.has(it.dc)) continue;
		if (hasCat) {
			let hit = false;
			for (const c of it.c)
				if (f.categories.has(c)) {
					hit = true;
					break;
				}
			if (!hit) continue;
		}
		if (terms.length) {
			const hay = catalog.haystack(it);
			let ok = true;
			for (const t of terms)
				if (!hay.includes(t)) {
					ok = false;
					break;
				}
			if (!ok) continue;
		}
		out.push(it);
	}
	// The prior comes from the whole pool, not the filtered subset, so narrowing
	// the filters cannot move an extension's rating relative to its peers.
	return sortItems(out, f.sort, f.sort === 'rating' ? ratingPrior(items) : 0);
}

function sortItems(items: IndexItem[], key: SortKey, prior: number): IndexItem[] {
	const cmp: Record<SortKey, (a: IndexItem, b: IndexItem) => number> = {
		score: (a, b) => b.sc - a.sc || b.u - a.u,
		users: (a, b) => b.u - a.u,
		// Nulls (unknown update date) sort last rather than first.
		updated: (a, b) => (a.ag ?? Infinity) - (b.ag ?? Infinity),
		rating: (a, b) => weightedRating(b, prior) - weightedRating(a, prior) || b.rc - a.rc,
		name: (a, b) => a.n.localeCompare(b.n)
	};
	return items.sort(cmp[key]);
}
