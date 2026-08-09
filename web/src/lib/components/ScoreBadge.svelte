<script lang="ts">
	import { bandClasses, cn, scoreBand } from '$lib/utils';

	interface Props {
		score: number;
		size?: 'sm' | 'md' | 'lg';
		class?: string;
	}
	let { score, size = 'md', class: klass }: Props = $props();

	const band = $derived(scoreBand(score));
	const sizes = {
		sm: 'h-6 min-w-6 px-1.5 text-[11px]',
		md: 'h-8 min-w-8 px-2 text-sm',
		lg: 'h-14 min-w-14 px-3 text-xl'
	};
</script>

<span
	class={cn(
		'tnum inline-flex items-center justify-center rounded-lg border font-semibold',
		sizes[size],
		bandClasses[band],
		klass
	)}
	title="Trust score {score} / 100"
>
	{score}
</span>
