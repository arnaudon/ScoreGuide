<script lang="ts">
	import { resolve } from '$app/paths';
	import ScoreDetailsDialog from '#lib/components/ScoreDetailsDialog.svelte';
	import EditScoreDialog from '#lib/components/EditScoreDialog.svelte';
	import AgentChat from '#lib/components/AgentChat.svelte';
	import ChatScores from '#lib/components/ChatScores.svelte';
	import ImslpSearch from '#lib/components/ImslpSearch.svelte';
	import ImslpAddDialog from '#lib/components/ImslpAddDialog.svelte';
	import BookOpenIcon from '@lucide/svelte/icons/book-open';
	import { composerName, matchesQuery, summarizeLibrary } from '#lib/library.js';
	import { aiRemaining } from '#lib/usage.js';
	import AiSwitch from '#lib/components/ai/AiSwitch.svelte';
	import NoAiTokens from '#lib/components/ai/NoAiTokens.svelte';
	import SearchIcon from '@lucide/svelte/icons/search';
	import { Input } from '#lib/components/ui/input/index.js';
	import { periodLabel } from '#lib/imslp.js';
	import { mainAgentHistoryStore } from '#lib/stores/chat.svelte.js';
	import type { ImslpResult, Score } from '#lib/types.js';
	import * as m from '#lib/paraglide/messages.js';

	let { form, data } = $props();
	let sheetOpen = $state(false);
	let editOpen = $state(false);
	let selectedScoreDetails = $state<Score | null>(null);
	let imslpWork = $state<ImslpResult | null>(null);
	let imslpOpen = $state(false);
	let addedScoreId = $state<number | null | undefined>(undefined);
	// After an edit or an AI rerun the page data reloads: show the fresh copy.
	let shownScore = $derived(
		(data.scores ?? []).find((s: Score) => s.id === selectedScoreDetails?.id) ??
			selectedScoreDetails
	);
	let summary = $derived(summarizeLibrary(data.scores ?? []));

	// The assistant is an extra: off (by choice, in the demo, or with no AI
	// tokens left) the card searches the library instead, for free.
	const AI_KEY = 'scoreguide.home.ai';
	const aiUsable = $derived(!data.isDemo && aiRemaining(data.user) > 0);
	let aiWanted = $state(true);
	$effect(() => {
		try {
			if (localStorage.getItem(AI_KEY) === 'off') aiWanted = false;
		} catch {
			// storage blocked: on
		}
	});
	function setAi(value: boolean) {
		aiWanted = value;
		try {
			localStorage.setItem(AI_KEY, value ? 'on' : 'off');
		} catch {
			// storage blocked: not remembered
		}
	}
	const aiOn = $derived(aiWanted && aiUsable);
	const SEARCH_SHOWN = 20;
	let query = $state('');
	const found = $derived(
		query.trim() ? (data.scores ?? []).filter((s: Score) => matchesQuery(s, query)) : []
	);
	let composerMax = $derived(Math.max(1, ...summary.topComposers.map((c) => c.count)));
	let periodMax = $derived(Math.max(1, ...summary.periods.map((p) => p.count)));

	/** The library scores an answer points to (several, or the one it picked). */
	function chatScores(msg: Record<string, unknown>): Score[] {
		if (Array.isArray(msg.scores) && msg.scores.length) return msg.scores as Score[];
		return msg.scoreDetails ? [msg.scoreDetails as Score] : [];
	}

	function onResult(data: Record<string, unknown>) {
		const answer = (data.answer ?? {}) as Record<string, unknown>;
		const inner = (answer.response ?? null) as Record<string, unknown> | string | null;
		let textAns: unknown =
			typeof inner === 'object' && inner !== null && 'response' in inner ? inner.response : inner;

		const scoreId = answer.score_id ?? (typeof inner === 'object' && inner ? inner.score_id : null);
		const scores = (data.scores as Score[] | undefined) ?? [];

		return {
			question: String(data.question ?? ''),
			answer: {
				answer: typeof textAns === 'string' ? textAns : JSON.stringify(textAns, null, 2),
				score_id: scoreId,
				scoreDetails: data.scoreDetails,
				scores
			},
			rawHistory: answer.message_history as unknown[] | undefined
		};
	}
</script>

<div class="mx-auto flex w-full max-w-5xl flex-col gap-8 pb-8">
	{#if data.hasScores === false}
		<div
			class="border-border bg-muted/50 text-muted-foreground mb-4 rounded-md border border-dashed p-4 text-center text-sm"
		>
			{m.empty_db_p1()}

			<a href={resolve('db-viewer')} class="text-primary font-medium hover:underline">
				{m.empty_db_link()}
			</a>

			{m.empty_db_p2()}
		</div>
	{/if}
	<!-- The assistant has a fixed height (the conversation scrolls inside), so
	     asking questions never pushes the rest of the page down. -->
	<div class="grid gap-6 lg:grid-cols-5">
		<section
			class="bg-card shadow-card flex h-[30rem] min-w-0 flex-col rounded-lg border p-4 sm:p-5 lg:h-[34rem] {data.isDemo
				? 'lg:col-span-5'
				: 'lg:col-span-3'}"
		>
			<div class="mb-2 flex flex-col items-end gap-1">
				<AiSwitch checked={aiOn} disabled={!aiUsable} onChange={setAi} />
				{#if data.isDemo}
					<p class="text-muted-foreground text-xs">{m.ai_demo_off()}</p>
				{:else if !aiUsable}
					<NoAiTokens />
				{/if}
			</div>
			{#if aiOn}
				<AgentChat
					{form}
					action="?/ask"
					title={m.hello_user({ name: data.user.username })}
					titleClass="text-fancy-title text-3xl leading-tight font-semibold sm:text-4xl"
					emptyMessage={m.what_to_play()}
					placeholder={m.agent_placeholder_main()}
					suggestions={[m.chat_suggest_easy(), m.chat_suggest_bach(), m.chat_suggest_surprise()]}
					{onResult}
					user={data.user}
					store={mainAgentHistoryStore}
				>
					{#snippet resultSnippet({ msg })}
						<p class="whitespace-pre-wrap">{msg.answer}</p>
						{@const found = chatScores(msg)}
						{#if found.length}
							<ChatScores
								scores={found}
								onSelect={(score) => {
									selectedScoreDetails = score;
									sheetOpen = true;
								}}
							/>
						{/if}
					{/snippet}
				</AgentChat>
			{:else}
				<div class="flex min-h-0 flex-1 flex-col gap-3">
					<h1
						class="text-fancy-title text-foreground text-3xl leading-tight font-semibold sm:text-4xl"
					>
						{m.hello_user({ name: data.user.username })}
						<span class="text-muted-foreground block">{m.what_to_play()}</span>
					</h1>
					<div class="relative">
						<SearchIcon
							class="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
							aria-hidden="true"
						/>
						<Input
							type="search"
							bind:value={query}
							aria-label={m.home_search_hint()}
							placeholder={m.home_search_hint()}
							class="h-10 pl-9"
						/>
					</div>
					<div class="min-h-0 flex-1 overflow-y-auto">
						{#if query.trim() && found.length === 0}
							<p class="text-muted-foreground text-sm">{m.home_search_none()}</p>
						{:else if found.length}
							<ChatScores
								scores={found.slice(0, SEARCH_SHOWN)}
								onSelect={(score) => {
									selectedScoreDetails = score;
									sheetOpen = true;
								}}
							/>
							{#if found.length > SEARCH_SHOWN}
								<a
									href={resolve('/db-viewer')}
									class="text-primary mt-2 inline-block text-sm font-medium hover:underline"
								>
									{m.home_search_more({ count: found.length - SEARCH_SHOWN })}
								</a>
							{/if}
						{/if}
					</div>
				</div>
			{/if}
		</section>
		{#if !data.isDemo}
			<section
				class="bg-card shadow-card flex min-w-0 flex-col gap-2 rounded-lg border p-4 sm:p-5 lg:col-span-2 lg:h-[34rem]"
				aria-labelledby="imslp-home-title"
			>
				<h2 id="imslp-home-title" class="text-foreground font-semibold">{m.imslp_home_title()}</h2>
				<p class="text-muted-foreground text-sm">{m.imslp_home_desc()}</p>
				<ImslpSearch
					preferredInstrument={data.user.instrument}
					class="lg:min-h-0 lg:flex-1"
					listClass="max-h-64 overflow-y-auto lg:max-h-none lg:min-h-0 lg:flex-1"
					onSelect={(work) => {
						imslpWork = work;
						addedScoreId = undefined;
						imslpOpen = true;
					}}
				/>
				{#if addedScoreId !== undefined}
					<p role="status" class="text-sm">
						{m.imslp_added()}
						{#if addedScoreId !== null}
							<a
								href={resolve('/reader/[id]', { id: String(addedScoreId) })}
								class="text-primary font-medium hover:underline"
							>
								{m.imslp_open_added()}
							</a>
						{/if}
					</p>
				{/if}
			</section>
		{/if}
	</div>
	{#if summary.total}
		<section aria-labelledby="home-continue" class="flex flex-col gap-3">
			<div class="flex items-baseline justify-between gap-4">
				<h2 id="home-continue" class="text-fancy-title text-foreground text-2xl font-semibold">
					{summary.continueIsRecent ? m.home_recent() : m.home_continue()}
				</h2>
				<a href={resolve('/db-viewer')} class="text-primary text-sm font-medium hover:underline">
					{m.home_see_library()}
				</a>
			</div>
			<ul class="grid grid-cols-2 gap-3 lg:grid-cols-4">
				{#each summary.continue as score (score.id)}
					<li>
						<a
							href={resolve('/reader/[id]', { id: String(score.id) })}
							class="bg-card shadow-card hover:border-primary/40 focus-visible:ring-ring group flex h-full flex-col gap-1 rounded-lg border p-3 transition-colors focus-visible:ring-2 focus-visible:outline-none sm:p-4"
						>
							<span
								class="text-muted-foreground truncate text-xs font-medium tracking-wide uppercase"
							>
								{composerName(score.composer)}
							</span>
							<span
								class="text-fancy-title text-foreground group-hover:text-primary line-clamp-3 text-base leading-snug font-semibold sm:text-lg"
							>
								{score.title}
							</span>
							<span class="text-muted-foreground mt-auto flex items-center gap-1.5 pt-2 text-xs">
								<BookOpenIcon class="size-3.5" aria-hidden="true" />
								{score.number_of_plays
									? m.home_played_times({ count: score.number_of_plays })
									: m.home_never_played()}
							</span>
						</a>
					</li>
				{/each}
			</ul>
		</section>

		<section aria-labelledby="home-repertoire" class="flex flex-col gap-3">
			<h2 id="home-repertoire" class="text-fancy-title text-foreground text-2xl font-semibold">
				{m.home_repertoire()}
			</h2>
			<dl class="grid grid-cols-3 gap-3">
				{#each [{ label: m.home_stat_scores(), value: summary.total }, { label: m.home_stat_composers(), value: summary.composers }, summary.plays ? { label: m.home_stat_plays(), value: summary.plays } : { label: m.home_stat_periods(), value: summary.periods.length }] as stat (stat.label)}
					<div
						class="bg-card shadow-card flex min-w-0 flex-col-reverse rounded-lg border p-3 sm:p-4"
					>
						<dt
							class="text-muted-foreground text-xs font-medium break-words hyphens-auto sm:text-sm"
						>
							{stat.label}
						</dt>
						<dd class="text-foreground text-2xl font-semibold tabular-nums sm:text-3xl">
							{stat.value}
						</dd>
					</div>
				{/each}
			</dl>
			<div class="grid grid-cols-1 gap-3 md:grid-cols-2">
				<div class="bg-card shadow-card rounded-lg border p-4">
					<h3 class="text-foreground font-semibold">{m.home_top_composers()}</h3>
					<p class="text-muted-foreground mb-3 text-xs">
						{summary.plays ? m.home_top_composers_plays() : m.home_top_composers_scores()}
					</p>
					<ul class="flex flex-col gap-2">
						{#each summary.topComposers as composer (composer.name)}
							<li class="grid grid-cols-[minmax(0,10rem)_1fr_2rem] items-center gap-3 text-sm">
								<span class="text-foreground truncate">{composer.name}</span>
								<span class="bg-muted h-2 overflow-hidden rounded-full" aria-hidden="true">
									<span
										class="bg-primary block h-full rounded-full"
										style="width: {(composer.count / composerMax) * 100}%"
									></span>
								</span>
								<span class="text-muted-foreground text-right tabular-nums">{composer.count}</span>
							</li>
						{/each}
					</ul>
				</div>
				<div class="bg-card shadow-card rounded-lg border p-4">
					<h3 class="text-foreground mb-3 font-semibold">{m.home_periods()}</h3>
					<ul class="flex flex-col gap-2">
						{#each summary.periods as period (period.name)}
							<li class="grid grid-cols-[minmax(0,10rem)_1fr_2rem] items-center gap-3 text-sm">
								<span class="text-foreground truncate">{periodLabel(period.name)}</span>
								<span class="bg-muted h-2 overflow-hidden rounded-full" aria-hidden="true">
									<span
										class="bg-primary/70 block h-full rounded-full"
										style="width: {(period.count / periodMax) * 100}%"
									></span>
								</span>
								<span class="text-muted-foreground text-right tabular-nums">{period.count}</span>
							</li>
						{/each}
					</ul>
					{#if summary.mostPlayed.length}
						<h3 class="text-foreground mt-4 mb-2 font-semibold">{m.home_most_played()}</h3>
						<ol class="flex flex-col gap-1 text-sm">
							{#each summary.mostPlayed as score (score.id)}
								<li class="flex justify-between gap-3">
									<a
										href={resolve('/reader/[id]', { id: String(score.id) })}
										class="text-foreground hover:text-primary truncate"
									>
										{score.title}
									</a>
									<span class="text-muted-foreground shrink-0 tabular-nums">
										{m.home_played_times({ count: score.number_of_plays })}
									</span>
								</li>
							{/each}
						</ol>
					{/if}
				</div>
			</div>
		</section>
	{/if}
</div>

<ScoreDetailsDialog
	score={shownScore}
	bind:open={sheetOpen}
	user={data.user}
	onEdit={() => (editOpen = true)}
/>

<EditScoreDialog bind:open={editOpen} score={shownScore} action="/db-viewer?/update_score" />

<ImslpAddDialog
	bind:work={imslpWork}
	bind:open={imslpOpen}
	action="/db-viewer?/add_imslp"
	onAdded={(id) => (addedScoreId = id)}
/>
