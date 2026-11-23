<script lang="ts">
	import { resolve } from '$app/paths';
	import BookOpenIcon from '@lucide/svelte/icons/book-open';
	import type { Score } from '#lib/types.js';
	import { composerName } from '#lib/library.js';
	import * as m from '#lib/paraglide/messages.js';

	/**
	 * Library scores an assistant answer points to: click a row for its details,
	 * or open it straight in the reader.
	 */
	let { scores, onSelect }: { scores: Score[]; onSelect?: (score: Score) => void } = $props();

	const SHOWN = 5;
	let showAll = $state(false);
	const visible = $derived(showAll ? scores : scores.slice(0, SHOWN));
</script>

<ul class="mt-3 flex flex-col gap-1.5">
	{#each visible as score (score.id)}
		<li
			class="bg-card hover:border-primary/40 flex items-center gap-2 rounded-lg border px-3 py-2 transition-colors"
		>
			<button
				type="button"
				class="min-w-0 flex-1 text-left"
				onclick={() => onSelect?.(score)}
				title={m.view_details()}
			>
				<span class="text-foreground block truncate font-medium">{score.title}</span>
				<span class="text-muted-foreground block truncate text-xs"
					>{composerName(score.composer)}</span
				>
			</button>
			<a
				href={resolve('/reader/[id]', { id: String(score.id) })}
				class="text-primary hover:bg-primary/10 inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-medium"
				><BookOpenIcon class="size-3.5" />{m.chat_open_score()}</a
			>
		</li>
	{/each}
</ul>
{#if !showAll && scores.length > SHOWN}
	<button
		type="button"
		class="text-primary mt-2 text-xs font-medium hover:underline"
		onclick={() => (showAll = true)}>{m.chat_more_scores({ count: scores.length - SHOWN })}</button
	>
{/if}
