import { base } from '$app/paths';
import type { ExtensionDetail, IndexItem, Meta } from './types';

export type SortKey = 'relevance' | 'score' | 'users' | 'updated' | 'rating' | 'name';

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

	/** Normalised search text per id, so query filtering never re-normalises 71k
	 *  strings on every keystroke. Keyed by id rather than object identity so it
	 *  stays correct regardless of any proxy wrapping. */
	#haystack = new Map<number, SearchFields>();

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
			this.#haystack.set(it.id, searchFields(it));
		}
	}

	fields(it: IndexItem): SearchFields {
		let h = this.#haystack.get(it.id);
		if (h === undefined) {
			h = searchFields(it);
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

// --- search ------------------------------------------------------------------

/**
 * Both fields are normalised and space-padded so a word-boundary test is a
 * plain `includes(' term ')` — no regex construction and no array of tokens per
 * extension, which at 71k records is the difference between a few megabytes and
 * a few tens of megabytes resident.
 */
interface SearchFields {
	/** ` normalised name `. */
	name: string;
	/** ` normalised name  normalised summary `. */
	all: string;
}

/**
 * Lowercase, strip accents, and reduce every run of punctuation to a single
 * space. Diacritics are folded so "übersicht" and "ubersicht" are the same
 * query, but the character classes are Unicode-aware: stripping to ASCII would
 * erase the Cyrillic, Chinese and Japanese titles the corpus is full of and
 * make them unsearchable in their own language.
 */
export function normalizeText(s: string): string {
	return s
		.normalize('NFKD')
		.replace(/[\u0300-\u036f]/g, '')
		.toLowerCase()
		.replace(/[^\p{L}\p{N}]+/gu, ' ')
		.trim();
}

function searchFields(it: IndexItem): SearchFields {
	const name = ` ${normalizeText(it.n)} `;
	return { name, all: `${name} ${normalizeText(it.d)} ` };
}

export function queryTerms(q: string): string[] {
	const n = normalizeText(q);
	return n ? n.split(' ') : [];
}

/** Weights are relative, not absolute — only their order matters. A hit in the
 *  name is worth far more than one in the summary, and an exact name is worth
 *  more than a name that merely contains the word. */
const HIT_EXACT_NAME = 100;
const HIT_NAME_WORD = 55;
const HIT_NAME_PREFIX = 40;
const HIT_NAME_SUBSTRING = 22;
const HIT_SUMMARY_WORD = 10;
const HIT_SUMMARY_SUBSTRING = 5;

function termScore(f: SearchFields, term: string): number {
	if (f.name === ` ${term} `) return HIT_EXACT_NAME;
	if (f.name.includes(` ${term} `)) return HIT_NAME_WORD;
	if (f.name.includes(` ${term}`)) return HIT_NAME_PREFIX;
	if (f.name.includes(term)) return HIT_NAME_SUBSTRING;
	if (f.all.includes(` ${term} `)) return HIT_SUMMARY_WORD;
	if (f.all.includes(term)) return HIT_SUMMARY_SUBSTRING;
	return 0;
}

/** True when `term` is within one edit of some word in `padded`. Used only as a
 *  fallback, so the cost of the inner loop is paid on failed searches alone. */
function fuzzyHit(padded: string, term: string): boolean {
	if (term.length < 4) return false;
	// Reject on the first letter before splitting. Splitting every name in the
	// corpus costs more than the whole rest of the search, and this pass runs
	// over the full pool by definition — the strict pass already found nothing.
	// The price is that a typo in a word's first letter is not corrected, which
	// is both the rarest kind and the one users notice themselves.
	if (!padded.includes(` ${term[0]}`)) return false;
	for (const word of padded.split(' ')) {
		if (!word || word[0] !== term[0]) continue;
		if (Math.abs(word.length - term.length) > 1) continue;
		if (withinOneEdit(word, term)) return true;
	}
	return false;
}

function withinOneEdit(a: string, b: string): boolean {
	if (a === b) return true;
	const [short, long] = a.length <= b.length ? [a, b] : [b, a];
	if (long.length - short.length > 1) return false;
	let i = 0;
	let j = 0;
	let edited = false;
	while (i < short.length && j < long.length) {
		if (short[i] === long[j]) {
			i += 1;
			j += 1;
			continue;
		}
		if (edited) return false;
		edited = true;
		// Same length means a substitution; otherwise the extra character is in
		// the longer string, so only it advances.
		if (short.length === long.length) i += 1;
		j += 1;
	}
	return true;
}

/**
 * How well an extension answers the query, or 0 for no match.
 *
 * Every term has to hit something — an AND, as before — but the strength of
 * each hit now varies, and the phrase and popularity bonuses break ties the way
 * a reader expects: searching "ublock" should surface uBlock Origin, not the
 * highest-trust extension that happens to mention it.
 */
export function relevance(
	it: IndexItem,
	f: SearchFields,
	terms: string[],
	phrase: string,
	fuzzy: boolean
): number {
	let total = 0;
	for (const term of terms) {
		let s = termScore(f, term);
		if (!s && fuzzy && fuzzyHit(f.name, term)) s = HIT_NAME_PREFIX / 2;
		if (!s) return 0;
		total += s;
	}
	total /= terms.length;

	if (terms.length > 1) {
		if (f.name.includes(phrase)) total += 45;
		else if (f.all.includes(phrase)) total += 12;
	}

	// Nudges, deliberately small: they order equally-relevant matches without
	// letting a popular or high-scoring extension outrank a better answer.
	total += Math.min(8, Math.log10(it.u + 1) * 2);
	total += (it.sc / 100) * 5;
	return total;
}

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
	const terms = queryTerms(f.query);
	const phrase = terms.join(' ');

	// Typo tolerance is a second sweep, run only when the first one found
	// nothing. Folding it into the first sweep was measurably worse: it charges
	// every ordinary search for a correction it does not need (144ms vs 92ms over
	// the full 71k pool) to save time only on searches that already failed.
	const out: IndexItem[] = [];
	const scores = terms.length ? new Map<number, number>() : null;
	collect(items, f, terms, phrase, false, out, scores);
	if (terms.length && !out.length) collect(items, f, terms, phrase, true, out, scores);

	return sortItems(
		out,
		f.sort,
		f.sort === 'rating' ? ratingPrior(items) : 0,
		f.sort === 'relevance' ? scores : null
	);
}

function collect(
	items: IndexItem[],
	f: Filters,
	terms: string[],
	phrase: string,
	fuzzy: boolean,
	out: IndexItem[],
	scores: Map<number, number> | null
): void {
	const hasCat = f.categories.size > 0;
	const hasLic = f.licenseFamilies.size > 0;
	const hasDc = f.dataCollection.size > 0;

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
			const score = relevance(it, catalog.fields(it), terms, phrase, fuzzy);
			if (!score) continue;
			scores?.set(it.id, score);
		}
		out.push(it);
	}
}

function sortItems(
	items: IndexItem[],
	key: SortKey,
	prior: number,
	scores: Map<number, number> | null
): IndexItem[] {
	const cmp: Record<SortKey, (a: IndexItem, b: IndexItem) => number> = {
		// With no query there is nothing to be relevant to, so it degrades to the
		// trust ranking rather than returning an arbitrary order.
		relevance: scores
			? (a, b) => (scores.get(b.id) ?? 0) - (scores.get(a.id) ?? 0) || b.sc - a.sc
			: (a, b) => b.sc - a.sc || b.u - a.u,
		score: (a, b) => b.sc - a.sc || b.u - a.u,
		users: (a, b) => b.u - a.u,
		// Nulls (unknown update date) sort last rather than first.
		updated: (a, b) => (a.ag ?? Infinity) - (b.ag ?? Infinity),
		rating: (a, b) => weightedRating(b, prior) - weightedRating(a, prior) || b.rc - a.rc,
		name: (a, b) => a.n.localeCompare(b.n)
	};
	return items.sort(cmp[key]);
}
