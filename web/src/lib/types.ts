/** Compact record shipped in the search index. Keys are short to keep the
 *  payload small — see scripts/build_index.py. */
export interface IndexItem {
	id: number;
	s: string; // slug
	n: string; // name
	d: string; // truncated summary
	ic: string | null; // icon cache key, or a full URL when non-standard
	l: string; // license slug
	lf: LicenseFamily;
	t: Tier;
	sc: number; // trust score
	u: number; // average daily users
	r: number; // rating average
	rc: number; // rating count
	c: string[]; // categories
	ag: number | null; // days since last update
	bh: boolean; // requests broad host access
	hp: number; // count of high-risk permissions
	dc: DataCollectionState;
	pr: string[]; // Mozilla promoted categories
	rh: string | null; // repo host
}

export type Tier = 'verified' | 'declared';
export type LicenseFamily =
	| 'permissive'
	| 'public-domain'
	| 'weak-copyleft'
	| 'copyleft'
	| 'strong-copyleft';
export type DataCollectionState = 'none' | 'declared' | 'undisclosed';

export interface ScoreComponent {
	points: number;
	max: number;
	label: string;
}

export interface ExtensionDetail {
	id: number;
	slug: string;
	name: string;
	summary: string;
	description: string;
	icon: string | null;
	authors: { name: string; url: string }[];
	license: {
		slug: string;
		name: string;
		family: LicenseFamily;
		url: string | null;
		isAmoDefault: boolean;
	};
	repo: { url: string; host: string; owner: string; name: string } | null;
	tier: Tier;
	score: number;
	components: Record<string, ScoreComponent>;
	permissions: {
		high: string[];
		medium: string[];
		low: string[];
		optional: string[];
		broadHostAccess: boolean;
	};
	permissionHelp: Record<string, string>;
	dataCollection: { state: DataCollectionState; required: string[]; optional: string[] };
	version: string | null;
	lastUpdated: string | null;
	created: string | null;
	ageDays: number | null;
	users: number;
	ratings: { average?: number; count?: number; text_count?: number };
	categories: string[];
	promoted: string[];
	amoUrl: string;
	homepage: string | null;
	supportUrl: string | null;
	hasPrivacyPolicy: boolean;
	hasEula: boolean;
	isExperimental: boolean;
	requiresPayment: boolean;
	xpiSize: number | null;
}

export interface Meta {
	generated: string;
	crawledTotal: number;
	listed: number;
	tiers: { verified: number; declared: number };
	excludedNonOss: number;
	licenses: Record<string, number>;
	categories: Record<string, number>;
	shardCount: number;
}
