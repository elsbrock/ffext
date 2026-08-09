import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { DataCollectionState, IndexItem, LicenseFamily } from './types';

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

/** Icon URLs are reconstructed from the addon id; see compact_icon() in the build script. */
export function iconUrl(item: Pick<IndexItem, 'id' | 'ic'>, size: 64 | 128 = 64): string | null {
	if (item.ic === null) return null;
	if (item.ic.startsWith('http')) return item.ic;
	const bucket = Math.floor(item.id / 1000);
	const q = item.ic ? `?modified=${item.ic}` : '';
	return `https://addons.mozilla.org/user-media/addon_icons/${bucket}/${item.id}-${size}.png${q}`;
}

export function formatUsers(n: number): string {
	if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
	if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1).replace(/\.0$/, '')}k`;
	return String(n);
}

export function formatBytes(n: number | null): string {
	if (!n) return '—';
	if (n >= 1e6) return `${(n / 1e6).toFixed(1)} MB`;
	if (n >= 1e3) return `${Math.round(n / 1e3)} kB`;
	return `${n} B`;
}

export function formatAge(days: number | null): string {
	if (days === null) return 'unknown';
	if (days < 1) return 'today';
	if (days < 30) return `${days}d ago`;
	if (days < 365) return `${Math.round(days / 30)}mo ago`;
	const y = days / 365;
	return `${y < 10 ? y.toFixed(1).replace(/\.0$/, '') : Math.round(y)}y ago`;
}

/** Score bands. Deliberately conservative: 'high' requires genuinely strong signals. */
export function scoreBand(score: number): 'high' | 'mid' | 'low' {
	if (score >= 75) return 'high';
	if (score >= 50) return 'mid';
	return 'low';
}

export const bandClasses: Record<'high' | 'mid' | 'low', string> = {
	high: 'text-[var(--color-trust-high)] border-[var(--color-trust-high)]/35 bg-[var(--color-trust-high)]/10',
	mid: 'text-[var(--color-trust-mid)] border-[var(--color-trust-mid)]/35 bg-[var(--color-trust-mid)]/10',
	low: 'text-[var(--color-trust-low)] border-[var(--color-trust-low)]/35 bg-[var(--color-trust-low)]/10'
};

export const licenseFamilyLabel: Record<LicenseFamily, string> = {
	permissive: 'Permissive',
	'public-domain': 'Public domain',
	'weak-copyleft': 'Weak copyleft',
	copyleft: 'Copyleft',
	'strong-copyleft': 'Strong copyleft'
};

export const dataCollectionLabel: Record<DataCollectionState, string> = {
	none: 'Collects no data',
	declared: 'Discloses collection',
	undisclosed: 'Not disclosed'
};

export const categoryLabel: Record<string, string> = {
	appearance: 'Appearance',
	'privacy-security': 'Privacy & Security',
	'photos-music-videos': 'Photos, Music & Video',
	tabs: 'Tabs',
	'feeds-news-blogging': 'Feeds, News & Blogging',
	'search-tools': 'Search Tools',
	other: 'Other',
	'web-development': 'Web Development',
	'social-communication': 'Social & Communication',
	'games-entertainment': 'Games & Entertainment',
	'language-support': 'Language Support',
	'download-management': 'Download Management',
	'alerts-updates': 'Alerts & Updates',
	bookmarks: 'Bookmarks',
	shopping: 'Shopping'
};

export function debounce<T extends (...args: never[]) => void>(fn: T, ms: number) {
	let t: ReturnType<typeof setTimeout>;
	return (...args: Parameters<T>) => {
		clearTimeout(t);
		t = setTimeout(() => fn(...args), ms);
	};
}
