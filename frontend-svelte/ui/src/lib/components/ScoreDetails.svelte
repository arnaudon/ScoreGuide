<script lang="ts">
	import PlayIcon from '@lucide/svelte/icons/circle-play';
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
	import type { IMSLPScore, Score } from '#lib/types.js';
	import { localizedField } from '#lib/i18n/score.js';
	import * as m from '#lib/paraglide/messages.js';

	/**
	 * Read-only overview of a score's metadata, shared by the library,
	 * the reader and the chat results. Empty fields are left out.
	 */
	let { score }: { score: Score | IMSLPScore } = $props();

	const rec = $derived(score as unknown as Record<string, unknown>);
	const str = (key: string) => {
		const v = rec[key];
		return v === null || v === undefined ? '' : String(v).trim();
	};

	const DIFFICULTY_TONE: Record<string, string> = {
		easy: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
		moderate: 'bg-sky-500/15 text-sky-700 dark:text-sky-300',
		intermediate: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
		advanced: 'bg-orange-500/15 text-orange-700 dark:text-orange-300',
		expert: 'bg-rose-500/15 text-rose-700 dark:text-rose-300'
	};

	let chips = $derived(
		[
			{ label: m.label_year(), value: str('year') },
			{ label: m.label_period(), value: str('period') },
			{ label: m.label_key_signature(), value: str('key') },
			{ label: m.label_instrumentation(), value: str('instrumentation') }
		].filter((c) => c.value)
	);
	let difficulty = $derived(str('difficulty'));
	let summary = $derived(localizedField(score, 'short_description'));
	let about = $derived(localizedField(score, 'long_description'));
	let facts = $derived(
		[
			{ label: m.label_genre(), value: str('genre') },
			{ label: m.label_form(), value: str('form') },
			{ label: m.label_style(), value: str('style') },
			{ label: m.label_notable_interpreters(), value: str('notable_interpreters') }
		].filter((f) => f.value)
	);
	let youtube = $derived(str('youtube_url'));
	let permlink = $derived(str('permlink'));
</script>

<div class="flex flex-col gap-5">
	{#if chips.length || difficulty}
		<ul class="flex flex-wrap gap-1.5" aria-label={m.score_details()}>
			{#each chips as chip (chip.label)}
				<li
					class="bg-muted text-foreground rounded-full px-2.5 py-0.5 text-xs font-medium"
					title={chip.label}
				>
					<span class="sr-only">{chip.label}: </span>{chip.value}
				</li>
			{/each}
			{#if difficulty}
				<li
					class={[
						'rounded-full px-2.5 py-0.5 text-xs font-medium capitalize',
						DIFFICULTY_TONE[difficulty] ?? 'bg-muted text-foreground'
					]}
					title={m.label_difficulty()}
				>
					<span class="sr-only">{m.label_difficulty()}: </span>{difficulty}
				</li>
			{/if}
		</ul>
	{/if}

	{#if summary}
		<p class="text-foreground text-base leading-relaxed">{summary}</p>
	{/if}

	{#if facts.length}
		<dl class="grid grid-cols-1 gap-x-6 gap-y-3 rounded-lg border p-4 sm:grid-cols-2">
			{#each facts as fact (fact.label)}
				<div class="min-w-0">
					<dt class="text-muted-foreground text-xs font-medium tracking-wide uppercase">
						{fact.label}
					</dt>
					<dd class="text-foreground mt-0.5 text-sm break-words">{fact.value}</dd>
				</div>
			{/each}
		</dl>
	{/if}

	{#if about}
		<p class="text-muted-foreground text-sm leading-relaxed whitespace-pre-line">{about}</p>
	{/if}

	{#if youtube || permlink}
		<div class="flex flex-wrap gap-2">
			{#if youtube}
				<a
					href={youtube}
					target="_blank"
					rel="external noopener noreferrer"
					class="hover:bg-accent inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium"
				>
					<PlayIcon class="size-4 text-rose-600" />
					{m.watch_on_youtube()}
				</a>
			{/if}
			{#if permlink}
				<a
					href={permlink}
					target="_blank"
					rel="external noopener noreferrer"
					class="hover:bg-accent inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium"
				>
					<ExternalLinkIcon class="size-4" />
					IMSLP
				</a>
			{/if}
		</div>
	{/if}
</div>
