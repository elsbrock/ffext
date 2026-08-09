<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '$lib/utils';

	interface Props {
		variant?: 'neutral' | 'accent' | 'high' | 'mid' | 'low' | 'outline';
		title?: string;
		class?: string;
		children: Snippet;
	}
	let { variant = 'neutral', title, class: klass, children }: Props = $props();

	const variants = {
		neutral: 'bg-[var(--bg-sunken)] text-[var(--fg-muted)] border-[var(--border)]',
		outline: 'bg-transparent text-[var(--fg-subtle)] border-[var(--border-strong)]',
		accent: 'bg-[var(--accent-soft)] text-[var(--accent)] border-[var(--accent)]/30',
		high: 'bg-[var(--color-trust-high)]/10 text-[var(--color-trust-high)] border-[var(--color-trust-high)]/30',
		mid: 'bg-[var(--color-trust-mid)]/10 text-[var(--color-trust-mid)] border-[var(--color-trust-mid)]/30',
		low: 'bg-[var(--color-trust-low)]/10 text-[var(--color-trust-low)] border-[var(--color-trust-low)]/30'
	};
</script>

<span
	{title}
	class={cn(
		'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap',
		variants[variant],
		klass
	)}
>
	{@render children()}
</span>
