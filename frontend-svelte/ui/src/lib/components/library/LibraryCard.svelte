<script lang="ts">
	import { resolve } from '$app/paths';
	import InfoIcon from '@lucide/svelte/icons/info';
	import { Button } from '#lib/components/ui/button/index.js';
	import ScoreThumb from './ScoreThumb.svelte';
	import FavoriteButton from './FavoriteButton.svelte';
	import { composerName } from '#lib/library.js';
	import { periodLabel } from '#lib/imslp.js';
	import { formLabel, genreLabel, keyLabel } from '#lib/metadata.js';
	import type { Score } from '#lib/types.js';
	import * as m from '#lib/paraglide/messages.js';

	/** One score of the library: opens the reader; the buttons star it or show its details. */
	let {
		score,
		canEdit = true,
		onDetails,
		onFavorite
	}: {
		score: Score;
		canEdit?: boolean;
		onDetails: (id: number) => void;
		onFavorite: (id: number, value: boolean) => void;
	} = $props();

	const badges = $derived(
		[
			score.period ? periodLabel(score.period) : '',
			score.form ? formLabel(score.form) : score.genre ? genreLabel(score.genre) : '',
			score.key ? keyLabel(score.key) : ''
		].filter(Boolean)
	);
	const details = $derived(
		[score.instrumentation, score.year ? String(score.year) : ''].filter(Boolean).join(' · ')
	);
</script>

<article
	class="bg-card shadow-card hover:border-primary/40 focus-within:ring-ring group relative flex h-full gap-3 rounded-lg border p-3 transition-colors focus-within:ring-2"
>
	<ScoreThumb scoreId={score.id} hasPdf={!!score.pdf_path} class="w-16 sm:w-[4.5rem]" />
	<div class="flex min-w-0 flex-1 flex-col gap-1">
		<span class="text-muted-foreground truncate text-xs font-medium tracking-wide uppercase">
			{composerName(score.composer)}
		</span>
		<a
			href={resolve('/reader/[id]', { id: String(score.id) })}
			class="text-fancy-title text-foreground group-hover:text-primary line-clamp-2 leading-snug font-semibold after:absolute after:inset-0 after:content-[''] focus-visible:outline-none"
		>
			{score.title}
		</a>
		{#if badges.length}
			<div class="flex flex-wrap gap-1">
				{#each badges as badge (badge)}
					<span
						class="bg-muted text-muted-foreground rounded px-1.5 py-0.5 text-[11px] leading-none"
					>
						{badge}
					</span>
				{/each}
			</div>
		{/if}
		{#if details}
			<span class="text-muted-foreground truncate text-xs">{details}</span>
		{/if}
		<span class="text-muted-foreground mt-auto pt-1 text-xs">
			{score.number_of_plays
				? m.home_played_times({ count: score.number_of_plays })
				: m.home_never_played()}
		</span>
	</div>
	<!-- Above the stretched link, so they don't open the reader. -->
	<div class="relative z-10 -my-1 -mr-1 flex flex-col">
		{#if canEdit}
			<FavoriteButton
				favorite={!!score.favorite}
				onToggle={(value: boolean) => onFavorite(score.id, value)}
			/>
		{/if}
		<Button
			variant="ghost"
			size="icon"
			class="size-8"
			aria-label={m.view_details()}
			title={m.view_details()}
			onclick={() => onDetails(score.id)}
		>
			<InfoIcon class="text-muted-foreground size-4" />
		</Button>
	</div>
</article>
