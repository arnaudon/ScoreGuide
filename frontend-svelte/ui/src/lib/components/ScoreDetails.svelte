<script lang="ts">
	import PlayIcon from '@lucide/svelte/icons/circle-play';
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
	import SearchIcon from '@lucide/svelte/icons/search';
	import BookOpenIcon from '@lucide/svelte/icons/book-open';
	import { youtubeEmbedUrl, youtubeSearchUrl, youtubeVideoId } from '#lib/youtube.js';
	import type { IMSLPScore, ImslpResult, Score } from '#lib/types.js';
	import { localizedField } from '#lib/i18n/score.js';
	import { httpUrl } from '#lib/url.js';
	import { parseDescription, type Inline } from '#lib/description.js';
	import * as m from '#lib/paraglide/messages.js';

	/**
	 * Read-only overview of a score's metadata, shared by the library,
	 * the reader and the chat results. Empty fields are left out.
	 */
	let { score }: { score: Score | IMSLPScore | ImslpResult } = $props();

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
		].filter((c) => c.value && c.value !== '0')
	);
	let difficulty = $derived(str('difficulty'));
	// Only library scores count plays (IMSLP results have no such field).
	let plays = $derived(
		typeof rec.number_of_plays === 'number' ? (rec.number_of_plays as number) : null
	);
	let summary = $derived(localizedField(score, 'short_description'));
	let about = $derived(parseDescription(localizedField(score, 'long_description')));
	/** A link shows its site (the full address is in the tooltip). */
	const linkLabel = (href: string) => {
		try {
			return new URL(href).hostname.replace(/^www\./, '');
		} catch {
			return href;
		}
	};
	let facts = $derived(
		[
			{ label: m.label_genre(), value: str('genre') },
			{ label: m.label_form(), value: str('form') },
			{ label: m.label_style(), value: str('style') },
			{ label: m.label_notable_interpreters(), value: str('notable_interpreters') }
		].filter((f) => f.value)
	);
	let youtube = $derived(httpUrl(str('youtube_url')));
	let videoId = $derived(youtubeVideoId(youtube));
	let search = $derived(str('title') ? youtubeSearchUrl(str('composer'), str('title')) : '');
	let permlink = $derived(httpUrl(str('permlink')));
	// Nothing is loaded from YouTube until the user asks to play.
	let playing = $state(false);
	$effect(() => {
		void videoId;
		playing = false;
	});
</script>

<div class="flex flex-col gap-5">
	{#if chips.length || difficulty || plays !== null}
		<div class="flex flex-wrap items-start gap-2">
			<ul class="flex flex-1 flex-wrap gap-1.5" aria-label={m.score_details()}>
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
			{#if plays !== null}
				<span
					class="text-muted-foreground ml-auto inline-flex shrink-0 items-center gap-1.5 text-xs font-medium"
				>
					<BookOpenIcon class="size-3.5" aria-hidden="true" />
					{plays ? m.home_played_times({ count: plays }) : m.home_never_played()}
				</span>
			{/if}
		</div>
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

	{#snippet inline(parts: Inline[])}
		{#each parts as part, i (i)}
			{#if part.href}
				<a
					href={part.href}
					title={part.href}
					target="_blank"
					rel="external noopener noreferrer"
					class="text-primary break-all hover:underline">{linkLabel(part.href)}</a
				>
			{:else}{part.text}{/if}
		{/each}
	{/snippet}

	{#if about.length}
		<div class="text-muted-foreground flex flex-col gap-2 text-sm leading-relaxed">
			{#each about as block, i (i)}
				{#if block.kind === 'heading'}
					<h3 class="text-foreground mt-2 text-base font-semibold first:mt-0">{block.text}</h3>
				{:else if block.kind === 'list'}
					<ul class="list-disc space-y-1 pl-5">
						{#each block.items as item, j (j)}
							<li>{@render inline(item)}</li>
						{/each}
					</ul>
				{:else}
					<p class="whitespace-pre-line">{@render inline(block.parts)}</p>
				{/if}
			{/each}
		</div>
	{/if}

	{#if videoId}
		{#if playing}
			<div class="aspect-video w-full overflow-hidden rounded-lg border bg-black">
				<iframe
					src={youtubeEmbedUrl(videoId)}
					title={m.watch_on_youtube()}
					class="size-full"
					allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
					referrerpolicy="strict-origin-when-cross-origin"
					allowfullscreen
				></iframe>
			</div>
		{:else}
			<button
				type="button"
				onclick={() => (playing = true)}
				class="bg-muted hover:bg-muted/70 flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-lg border transition-colors"
			>
				<PlayIcon class="size-12 text-rose-600" />
				<span class="text-sm font-medium">{m.youtube_play_here()}</span>
				<span class="text-muted-foreground px-4 text-xs">{m.youtube_privacy_note()}</span>
			</button>
		{/if}
	{/if}

	{#if youtube || search || permlink}
		<div class="flex flex-wrap gap-2">
			{#if search}
				<a
					href={search}
					target="_blank"
					rel="external noopener noreferrer"
					class="hover:bg-accent inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium"
				>
					<SearchIcon class="size-4 text-rose-600" />
					{m.youtube_search()}
				</a>
			{/if}
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
