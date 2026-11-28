<script lang="ts">
	import type { PageProps, Snapshot } from './$types';
	import { resolve } from '$app/paths';
	import { enhance } from '$app/forms';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';
	import * as Table from '#lib/components/ui/table/index.js';
	import * as Popover from '#lib/components/ui/popover/index.js';
	import ScoreDetailsDialog from '#lib/components/ScoreDetailsDialog.svelte';
	import AiEffortSelect from '#lib/components/AiEffortSelect.svelte';
	import AiBadge from '#lib/components/ai/AiBadge.svelte';
	import LibraryCard from '#lib/components/library/LibraryCard.svelte';
	import FilterChip from '#lib/components/library/FilterChip.svelte';
	import FavoriteButton from '#lib/components/library/FavoriteButton.svelte';
	import ScoreThumb from '#lib/components/library/ScoreThumb.svelte';
	import InfoIcon from '@lucide/svelte/icons/info';
	import SearchIcon from '@lucide/svelte/icons/search';
	import StarIcon from '@lucide/svelte/icons/star';
	import LibraryIcon from '@lucide/svelte/icons/library-big';
	import XIcon from '@lucide/svelte/icons/x';
	import ArrowDownUpIcon from '@lucide/svelte/icons/arrow-down-up';
	import LayoutGridIcon from '@lucide/svelte/icons/layout-grid';
	import ListIcon from '@lucide/svelte/icons/list';
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down';
	import * as Tabs from '#lib/components/ui/tabs/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import {
		type ColumnDef,
		type ColumnFiltersState,
		type PaginationState,
		type SortingState,
		FlexRender,
		createTable,
		renderComponent
	} from '@tanstack/svelte-table';
	import { listFeatures, type ListFeatures } from '#lib/tables.js';
	import type { Score, IMSLPScore, ImslpResult } from '#lib/types.js';
	import ImslpSearch from '#lib/components/ImslpSearch.svelte';
	import ImslpAddDialog from '#lib/components/ImslpAddDialog.svelte';
	import AgentChat from '#lib/components/AgentChat.svelte';
	import EditScoreDialog from '#lib/components/EditScoreDialog.svelte';
	import DataTableSortButton from './data-table-sort-button.svelte';
	import { imslpAgentHistoryStore } from '#lib/stores/chat.svelte.js';
	import * as m from '#lib/paraglide/messages.js';
	import { aiLeftLabel, formatBytes } from '#lib/usage.js';
	import { periodLabel } from '#lib/imslp.js';
	import { formLabel, genreLabel, keyLabel } from '#lib/metadata.js';
	import {
		type Facet,
		type LibraryFilters,
		type LibrarySort,
		type SortKey,
		SORTS,
		SORT_DESC,
		composerName,
		emptyFilters,
		facetCounts,
		filterScores,
		groupByComposer,
		hasFilters,
		recentlyPlayed,
		sortScores
	} from '#lib/library.js';

	let { data, form }: PageProps = $props();
	let selectedScoreId = $state<number | null>(null);
	let agentSelectedScore = $state<IMSLPScore | ImslpResult | null>(null);
	let imslpSheetOpen = $state(false);
	let uploading = $state(false);
	let sheetOpen = $state(false);
	let editOpen = $state(false);
	let manualFiles = $state<FileList | undefined>();

	const isDemo = $derived(!!page.data.isDemo);
	// An empty library opens on "Add a score".
	let tab = $state(
		untrack(() => (data.scores.length === 0 && !page.data.isDemo ? 'add' : 'library'))
	);

	function openDetails(id: number) {
		selectedScoreId = id;
		sheetOpen = true;
	}

	// --- Favourites: shown at once, saved in the background ---------------------
	const favorites = new SvelteMap<number, boolean>();
	const scores = $derived(
		data.scores.map((s: Score) =>
			favorites.has(s.id) ? { ...s, favorite: favorites.get(s.id) } : s
		)
	);
	let selectedScore = $derived(scores.find((s: Score) => s.id === selectedScoreId));

	// Per score, the latest request: an older answer arriving late is ignored.
	const favoriteRequests = new Map<number, number>();
	async function setFavorite(id: number, value: boolean) {
		const previous = favorites.get(id) ?? !!data.scores.find((s: Score) => s.id === id)?.favorite;
		const request = (favoriteRequests.get(id) ?? 0) + 1;
		favoriteRequests.set(id, request);
		favorites.set(id, value);
		let ok = false;
		try {
			const res = await fetch(`/api/scores/${id}/favorite`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ favorite: value })
			});
			ok = res.ok;
		} catch {
			ok = false;
		}
		if (!ok && favoriteRequests.get(id) === request) favorites.set(id, previous);
	}
	// Once the page data agrees (after a reload of it), the overlay can go.
	$effect(() => {
		for (const s of data.scores as Score[]) {
			if (favorites.has(s.id) && favorites.get(s.id) === !!s.favorite) favorites.delete(s.id);
		}
	});

	// --- Browsing: search, filters, sort, then an ever longer list ----------------
	const STEP = 30;
	let filters = $state<LibraryFilters>(emptyFilters());
	let sort = $state<LibrarySort>({ key: 'composer', desc: false });
	let limit = $state(STEP);

	function setFilters(patch: Partial<LibraryFilters>) {
		filters = { ...filters, ...patch };
		limit = STEP;
	}
	function setSort(key: SortKey, desc = SORT_DESC[key]) {
		sort = { key, desc };
		limit = STEP;
	}
	function toggleColumnSort(key: SortKey) {
		setSort(key, sort.key === key ? !sort.desc : SORT_DESC[key]);
	}
	function clearFilters() {
		filters = emptyFilters();
		limit = STEP;
	}

	const filtered = $derived(sortScores(filterScores(scores, filters), sort));
	const shown = $derived(filtered.slice(0, limit));
	const groups = $derived(groupByComposer(shown, sort.key === 'composer'));
	const filtering = $derived(hasFilters(filters));
	const recent = $derived(recentlyPlayed(scores));
	const counts = $derived(
		Object.fromEntries(
			(['composer', 'period', 'genre', 'form', 'key'] as Facet[]).map((f) => [
				f,
				facetCounts(scores, f, filters)
			])
		) as Record<Facet, ReturnType<typeof facetCounts>>
	);
	const anyFavorite = $derived(scores.some((s: Score) => s.favorite));
	const anyCollection = $derived(scores.some((s: Score) => s.collection));

	const FACET_UI: {
		facet: Exclude<Facet, 'composer'>;
		label: () => string;
		value: (v: string) => string;
	}[] = [
		{ facet: 'period', label: m.label_period, value: periodLabel },
		{ facet: 'genre', label: m.label_genre, value: genreLabel },
		{ facet: 'form', label: m.label_form, value: formLabel },
		{ facet: 'key', label: m.label_key_signature, value: keyLabel }
	];
	const facetLabel = (facet: Facet, value: string) =>
		facet === 'composer' ? value : (FACET_UI.find((f) => f.facet === facet)?.value(value) ?? value);
	const activeValues = $derived(
		(['composer', 'period', 'genre', 'form', 'key'] as Facet[]).flatMap((facet) =>
			filters[facet].map((value) => ({ facet, value }))
		)
	);

	const SORT_LABELS: Record<SortKey, () => string> = {
		composer: m.sort_composer,
		title: m.sort_title,
		year: m.sort_year,
		plays: m.sort_plays,
		played: m.sort_played,
		added: m.sort_added
	};

	/** Loads the next scores when the end of the list scrolls into view. */
	function onVisible(node: HTMLElement) {
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries.some((e) => e.isIntersecting) && limit < filtered.length) limit += STEP;
			},
			{ rootMargin: '400px' }
		);
		observer.observe(node);
		return { destroy: () => observer.disconnect() };
	}

	// Cards or list, remembered on this device.
	const VIEW_KEY = 'scoreguide.library.view';
	let view = $state<'cards' | 'list'>('cards');
	$effect(() => {
		try {
			if (localStorage.getItem(VIEW_KEY) === 'list') view = 'list';
		} catch {
			// storage blocked: cards
		}
	});
	function setView(value: 'cards' | 'list') {
		view = value;
		try {
			localStorage.setItem(VIEW_KEY, value);
		} catch {
			// storage blocked: not remembered
		}
	}

	// Back from the reader: same filters, same sort, same length of list (the
	// browser then restores the scroll position).
	export const snapshot: Snapshot<{
		filters: LibraryFilters;
		sort: LibrarySort;
		limit: number;
		tab: string;
	}> = {
		capture: () => ({ filters, sort, limit, tab }),
		restore: (value) => {
			filters = value.filters;
			sort = value.sort;
			limit = value.limit;
			tab = value.tab;
		}
	};

	let imslpPagination = $state<PaginationState>({ pageIndex: 0, pageSize: 5 });
	let imslpSorting = $state<SortingState>([]);
	let imslpColumnFilters = $state<ColumnFiltersState>([]);

	const imslpColumns: ColumnDef<ListFeatures, IMSLPScore>[] = [
		{
			accessorKey: 'composer',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.label_composer(),
					onclick: column.getToggleSortingHandler()
				})
		},
		{
			accessorKey: 'title',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.label_title(),
					onclick: column.getToggleSortingHandler()
				})
		},
		{
			accessorKey: 'instrumentation',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.label_instrumentation(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) => row.original.instrumentation || '-'
		},
		{
			accessorKey: 'year',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.label_year(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) => row.original.year || '-'
		}
	];

	let imslpScores = $state<IMSLPScore[]>([]);
	function onImslpResult(data: Record<string, unknown>) {
		const res = (data.agent_results ?? {}) as Record<string, unknown>;
		const scores = (res.scores as IMSLPScore[] | undefined) ?? [];
		imslpScores = scores;
		return {
			question: String(data.question ?? ''),
			answer: {
				answer: res.response,
				scores: scores
			},
			rawHistory: res.message_history as unknown[] | undefined
		};
	}

	const imslpTable = createTable({
		features: listFeatures,
		autoResetPageIndex: false,
		get data() {
			return imslpScores;
		},
		columns: imslpColumns,
		state: {
			get pagination() {
				return imslpPagination;
			},
			get sorting() {
				return imslpSorting;
			},
			get columnFilters() {
				return imslpColumnFilters;
			}
		},
		onPaginationChange: (updater) => {
			if (typeof updater === 'function') {
				imslpPagination = updater(imslpPagination);
			} else {
				imslpPagination = updater;
			}
		},
		onSortingChange: (updater) => {
			if (typeof updater === 'function') {
				imslpSorting = updater(imslpSorting);
			} else {
				imslpSorting = updater;
			}
			imslpPagination = { ...imslpPagination, pageIndex: 0 };
		},
		onColumnFiltersChange: (updater) => {
			if (typeof updater === 'function') {
				imslpColumnFilters = updater(imslpColumnFilters);
			} else {
				imslpColumnFilters = updater;
			}
			imslpPagination = { ...imslpPagination, pageIndex: 0 };
		}
	});

	// v9's automatic page reset is off: keep the page valid when rows go away.
	$effect(() => {
		const pages = imslpTable.getPageCount();
		if (pages > 0 && imslpPagination.pageIndex >= pages)
			imslpPagination = { ...imslpPagination, pageIndex: pages - 1 };
	});
</script>

{#snippet facetList(facet: Facet, options: { name: string; count: number }[])}
	<ul class="flex flex-col">
		{#each options as option (option.name)}
			{@const on = filters[facet].includes(option.name)}
			<li>
				<button
					type="button"
					aria-pressed={on}
					class="hover:bg-accent flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors {on
						? 'bg-primary/10 text-primary font-medium'
						: 'text-foreground'}"
					onclick={() =>
						setFilters({
							[facet]: on
								? filters[facet].filter((v) => v !== option.name)
								: [...filters[facet], option.name]
						})}
				>
					<span class="min-w-0 flex-1 truncate">{facetLabel(facet, option.name)}</span>
					<span class="text-muted-foreground text-xs tabular-nums">{option.count}</span>
				</button>
			</li>
		{/each}
	</ul>
{/snippet}

<div class="p-4 sm:p-8">
	<Tabs.Root bind:value={tab} class="w-full gap-6">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<h1 class="text-fancy-title text-foreground text-2xl font-bold">{m.database_viewer()}</h1>
			{#if !isDemo}
				<Tabs.List>
					<Tabs.Trigger value="library">{m.database_viewer()}</Tabs.Trigger>
					<Tabs.Trigger value="add">{m.add_new_score()}</Tabs.Trigger>
				</Tabs.List>
			{/if}
		</div>
		<Tabs.Content value="library">
			<div class="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
				<!-- Composers: the way musicians browse. A chip below lg. -->
				<aside class="hidden lg:block" aria-labelledby="library-composers">
					<div class="sticky top-4 flex max-h-[calc(100vh-2rem)] flex-col gap-2">
						<h2
							id="library-composers"
							class="text-muted-foreground px-2 text-xs font-medium tracking-wide uppercase"
						>
							{m.library_composers()}
						</h2>
						<button
							type="button"
							class="hover:bg-accent flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm {filters
								.composer.length === 0
								? 'bg-primary/10 text-primary font-medium'
								: ''}"
							onclick={() => setFilters({ composer: [] })}
						>
							<span class="flex-1">{m.library_all_composers()}</span>
							<span class="text-muted-foreground text-xs tabular-nums">{scores.length}</span>
						</button>
						<div class="min-h-0 overflow-y-auto">
							{@render facetList('composer', counts.composer)}
						</div>
					</div>
				</aside>

				<div class="flex min-w-0 flex-col gap-4">
					{#if recent.length && !filtering}
						<section aria-labelledby="library-recent" class="flex flex-col gap-2">
							<h2
								id="library-recent"
								class="text-muted-foreground text-xs font-medium tracking-wide uppercase"
							>
								{m.library_recent()}
							</h2>
							<ul class="-mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-2">
								{#each recent as score (score.id)}
									<li class="w-56 shrink-0 snap-start">
										<a
											href={resolve('/reader/[id]', { id: String(score.id) })}
											class="bg-card shadow-card hover:border-primary/40 focus-visible:ring-ring group flex h-full items-center gap-3 rounded-lg border p-2 transition-colors focus-visible:ring-2 focus-visible:outline-none"
										>
											<ScoreThumb scoreId={score.id} hasPdf={!!score.pdf_path} class="w-10" />
											<span class="flex min-w-0 flex-col">
												<span class="text-muted-foreground truncate text-[11px] uppercase">
													{composerName(score.composer)}
												</span>
												<span
													class="group-hover:text-primary line-clamp-2 text-sm leading-snug font-medium"
												>
													{score.title}
												</span>
											</span>
										</a>
									</li>
								{/each}
							</ul>
						</section>
					{/if}

					<div class="relative">
						<SearchIcon
							class="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
							aria-hidden="true"
						/>
						<Input
							type="search"
							aria-label={m.library_search()}
							placeholder={m.library_search()}
							value={filters.query}
							oninput={(e) => setFilters({ query: e.currentTarget.value })}
							class="h-10 pl-9"
						/>
					</div>

					<div class="flex flex-wrap items-center gap-2">
						<FilterChip
							class="lg:hidden"
							label={m.sort_composer()}
							options={counts.composer}
							selected={filters.composer}
							onChange={(values: string[]) => setFilters({ composer: values })}
						/>
						{#each FACET_UI as f (f.facet)}
							{#if counts[f.facet].length || filters[f.facet].length}
								<FilterChip
									label={f.label()}
									options={counts[f.facet]}
									selected={filters[f.facet]}
									valueLabel={f.value}
									onChange={(values: string[]) => setFilters({ [f.facet]: values })}
								/>
							{/if}
						{/each}
						<Popover.Root>
							<Popover.Trigger
								class="hover:bg-accent focus-visible:ring-ring inline-flex h-8 items-center gap-1 rounded-full border px-3 text-sm transition-colors focus-visible:ring-2 focus-visible:outline-none {filters.yearMin !==
									null || filters.yearMax !== null
									? 'border-primary bg-primary/10 text-primary'
									: ''}"
							>
								{m.label_year()}
								{#if filters.yearMin !== null || filters.yearMax !== null}
									<span class="text-xs tabular-nums">
										{filters.yearMin ?? '…'}–{filters.yearMax ?? '…'}
									</span>
								{/if}
								<ChevronDownIcon class="size-3.5 opacity-60" aria-hidden="true" />
							</Popover.Trigger>
							<Popover.Content class="flex items-center gap-2 p-3">
								<Input
									type="number"
									aria-label={m.min()}
									placeholder={m.min()}
									value={filters.yearMin ?? ''}
									oninput={(e) =>
										setFilters({
											yearMin: e.currentTarget.value ? parseInt(e.currentTarget.value, 10) : null
										})}
									class="w-24"
								/>
								<span aria-hidden="true">–</span>
								<Input
									type="number"
									aria-label={m.max()}
									placeholder={m.max()}
									value={filters.yearMax ?? ''}
									oninput={(e) =>
										setFilters({
											yearMax: e.currentTarget.value ? parseInt(e.currentTarget.value, 10) : null
										})}
									class="w-24"
								/>
							</Popover.Content>
						</Popover.Root>
						{#if !isDemo && (anyFavorite || filters.favorites)}
							<button
								type="button"
								aria-pressed={filters.favorites}
								class="hover:bg-accent focus-visible:ring-ring inline-flex h-8 items-center gap-1 rounded-full border px-3 text-sm transition-colors focus-visible:ring-2 focus-visible:outline-none {filters.favorites
									? 'border-primary bg-primary/10 text-primary'
									: ''}"
								onclick={() => setFilters({ favorites: !filters.favorites })}
							>
								<StarIcon
									class="size-3.5 {filters.favorites ? 'fill-primary' : ''}"
									aria-hidden="true"
								/>
								{m.filter_favorites()}
							</button>
						{/if}
						{#if anyCollection || filters.collections}
							<button
								type="button"
								aria-pressed={filters.collections}
								class="hover:bg-accent focus-visible:ring-ring inline-flex h-8 items-center gap-1 rounded-full border px-3 text-sm transition-colors focus-visible:ring-2 focus-visible:outline-none {filters.collections
									? 'border-primary bg-primary/10 text-primary'
									: ''}"
								onclick={() => setFilters({ collections: !filters.collections })}
							>
								<LibraryIcon class="size-3.5" aria-hidden="true" />
								{m.filter_collections()}
							</button>
						{/if}
						{#if filtering}
							<Button variant="ghost" size="sm" class="h-8" onclick={clearFilters}>
								{m.filter_clear()}
							</Button>
						{/if}

						<div class="ml-auto flex items-center gap-1">
							<label for="library-sort" class="sr-only">{m.sort_label()}</label>
							<select
								id="library-sort"
								value={sort.key}
								onchange={(e) => setSort(e.currentTarget.value as SortKey)}
								class="border-input bg-background focus-visible:ring-ring h-8 rounded-md border px-2 text-sm focus-visible:ring-2 focus-visible:outline-none"
							>
								{#each SORTS as key (key)}
									<option value={key}>{SORT_LABELS[key]()}</option>
								{/each}
							</select>
							<Button
								variant="ghost"
								size="icon"
								class="size-8"
								aria-label={m.sort_reverse()}
								title={m.sort_reverse()}
								aria-pressed={sort.desc !== SORT_DESC[sort.key]}
								onclick={() => setSort(sort.key, !sort.desc)}
							>
								<ArrowDownUpIcon class="size-4" />
							</Button>
							<div
								class="ml-1 flex rounded-md border p-0.5"
								role="group"
								aria-label={m.view_list()}
							>
								<Button
									variant={view === 'cards' ? 'secondary' : 'ghost'}
									size="icon"
									class="size-7"
									aria-label={m.view_cards()}
									title={m.view_cards()}
									aria-pressed={view === 'cards'}
									onclick={() => setView('cards')}
								>
									<LayoutGridIcon class="size-4" />
								</Button>
								<Button
									variant={view === 'list' ? 'secondary' : 'ghost'}
									size="icon"
									class="size-7"
									aria-label={m.view_list()}
									title={m.view_list()}
									aria-pressed={view === 'list'}
									onclick={() => setView('list')}
								>
									<ListIcon class="size-4" />
								</Button>
							</div>
						</div>
					</div>

					{#if activeValues.length}
						<ul class="flex flex-wrap gap-1.5" aria-label={m.filter_clear()}>
							{#each activeValues as item (item.facet + item.value)}
								<li>
									<button
										type="button"
										class="bg-primary/10 text-primary hover:bg-primary/20 inline-flex items-center gap-1 rounded-full py-0.5 pr-1.5 pl-2.5 text-xs"
										aria-label={m.filter_remove({ name: facetLabel(item.facet, item.value) })}
										onclick={() =>
											setFilters({
												[item.facet]: filters[item.facet].filter((v) => v !== item.value)
											})}
									>
										{facetLabel(item.facet, item.value)}
										<XIcon class="size-3" aria-hidden="true" />
									</button>
								</li>
							{/each}
						</ul>
					{/if}

					<p class="text-muted-foreground text-sm" aria-live="polite">
						{m.library_showing({ shown: shown.length, total: filtered.length })}
					</p>

					{#if filtered.length === 0}
						<div
							class="text-muted-foreground rounded-lg border border-dashed p-8 text-center text-sm"
						>
							{#if scores.length === 0}
								<p>{m.library_empty()}</p>
								{#if !isDemo}
									<Button class="mt-3" onclick={() => (tab = 'add')}>{m.add_new_score()}</Button>
								{/if}
							{:else}
								<p>{m.library_no_match()}</p>
								<Button variant="outline" class="mt-3" onclick={clearFilters}>
									{m.filter_clear()}
								</Button>
							{/if}
						</div>
					{:else if view === 'cards'}
						<div class="flex flex-col gap-6">
							{#each groups as group (group.heading + group.scores[0].id)}
								<section class="flex flex-col gap-3">
									{#if group.heading}
										<h3
											class="text-fancy-title text-foreground flex items-baseline gap-2 text-lg font-semibold"
										>
											{group.heading}
											<span class="text-muted-foreground text-sm font-normal tabular-nums">
												{counts.composer.find((c) => c.name === group.heading)?.count ??
													group.scores.length}
											</span>
										</h3>
									{/if}
									<ul class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
										{#each group.scores as score (score.id)}
											<li>
												<LibraryCard
													{score}
													canEdit={!isDemo}
													onDetails={openDetails}
													onFavorite={setFavorite}
												/>
											</li>
										{/each}
									</ul>
								</section>
							{/each}
						</div>
					{:else}
						<div class="bg-card text-card-foreground shadow-card overflow-x-auto rounded-md border">
							<Table.Root>
								<Table.Header>
									<Table.Row>
										{#each [{ key: 'title', label: m.label_title() }, { key: 'composer', label: m.label_composer() }] as col (col.key)}
											<Table.Head>
												<DataTableSortButton
													title={col.label}
													onclick={() => toggleColumnSort(col.key as SortKey)}
												/>
											</Table.Head>
										{/each}
										<Table.Head class="hidden md:table-cell">
											{m.label_instrumentation()}
										</Table.Head>
										<Table.Head>
											<DataTableSortButton
												title={m.label_year()}
												onclick={() => toggleColumnSort('year')}
											/>
										</Table.Head>
										<Table.Head class="hidden lg:table-cell">{m.label_period()}</Table.Head>
										<Table.Head class="hidden lg:table-cell">{m.label_genre()}</Table.Head>
										<Table.Head class="hidden sm:table-cell">
											<DataTableSortButton
												title={m.home_stat_plays()}
												onclick={() => toggleColumnSort('plays')}
											/>
										</Table.Head>
										<Table.Head class="hidden xl:table-cell">{m.label_size()}</Table.Head>
										<Table.Head><span class="sr-only">{m.view_details()}</span></Table.Head>
									</Table.Row>
								</Table.Header>
								<Table.Body>
									{#each groups as group (group.heading + group.scores[0].id)}
										{#if group.heading}
											<Table.Row class="bg-muted/40 hover:bg-muted/40">
												<Table.Cell
													colspan={9}
													class="text-foreground py-1.5 text-sm font-semibold"
												>
													{group.heading}
												</Table.Cell>
											</Table.Row>
										{/if}
										{#each group.scores as score (score.id)}
											<Table.Row class="hover:bg-muted/50 relative transition-colors">
												<Table.Cell class="max-w-[16rem]">
													<a
														href={resolve('/reader/[id]', { id: String(score.id) })}
														class="hover:text-primary line-clamp-2 font-medium after:absolute after:inset-0 after:content-['']"
													>
														{score.title}
													</a>
												</Table.Cell>
												<Table.Cell class="max-w-[12rem] truncate">
													{composerName(score.composer)}
												</Table.Cell>
												<Table.Cell class="hidden max-w-[12rem] truncate md:table-cell">
													{score.instrumentation || '-'}
												</Table.Cell>
												<Table.Cell class="tabular-nums">{score.year || '-'}</Table.Cell>
												<Table.Cell class="hidden lg:table-cell">
													{score.period ? periodLabel(score.period) : '-'}
												</Table.Cell>
												<Table.Cell class="hidden lg:table-cell">
													{score.genre ? genreLabel(score.genre) : '-'}
												</Table.Cell>
												<Table.Cell class="hidden tabular-nums sm:table-cell">
													{score.number_of_plays ?? 0}
												</Table.Cell>
												<Table.Cell class="hidden xl:table-cell">
													{score.pdf_size ? formatBytes(score.pdf_size) : '-'}
												</Table.Cell>
												<Table.Cell class="relative z-10 w-0 py-1 text-right whitespace-nowrap">
													{#if !isDemo}
														<FavoriteButton
															favorite={!!score.favorite}
															onToggle={(value: boolean) => setFavorite(score.id, value)}
														/>
													{/if}
													<Button
														variant="ghost"
														size="icon"
														class="size-8"
														aria-label={m.view_details()}
														title={m.view_details()}
														onclick={() => openDetails(score.id)}
													>
														<InfoIcon class="size-4" />
													</Button>
												</Table.Cell>
											</Table.Row>
										{/each}
									{/each}
								</Table.Body>
							</Table.Root>
						</div>
					{/if}

					{#if shown.length < filtered.length}
						{#key limit}
							<div use:onVisible class="flex justify-center py-2">
								<Button variant="outline" onclick={() => (limit += STEP)}>
									{m.library_load_more()}
								</Button>
							</div>
						{/key}
					{/if}
				</div>
			</div>
		</Tabs.Content>
		{#if !isDemo}
			<Tabs.Content value="add">
				<div class="bg-card text-card-foreground shadow-card rounded-md border p-4">
					<div class="mb-4 flex items-center justify-between gap-2">
						<h2 class="text-fancy-title text-lg font-semibold">{m.add_new_score()}</h2>
						{#if aiLeftLabel(data.user)}
							<span class="text-muted-foreground text-sm font-medium">
								{aiLeftLabel(data.user)}
							</span>
						{/if}
					</div>
					<Tabs.Root value="manual" class="w-full">
						<Tabs.List class="mb-4">
							<Tabs.Trigger value="manual">{m.manual_upload()}</Tabs.Trigger>
							<Tabs.Trigger value="imslp">{m.from_imslp()}</Tabs.Trigger>
						</Tabs.List>
						<Tabs.Content value="manual">
							<form
								method="POST"
								action="?/upload"
								enctype="multipart/form-data"
								use:enhance={() => {
									uploading = true;
									return async ({ update }) => {
										uploading = false;
										manualFiles = undefined;
										update();
									};
								}}
								class="flex flex-col gap-4 md:flex-row md:flex-wrap md:items-end"
							>
								<div class="flex-1 space-y-2">
									<label for="title" class="text-sm leading-none font-medium">{m.title()}</label>
									<Input id="title" name="title" required />
								</div>
								<div class="flex-1 space-y-2">
									<label for="composer" class="text-sm leading-none font-medium">
										{m.composer()}
									</label>
									<Input id="composer" name="composer" required />
								</div>
								<div class="flex-1 space-y-2">
									<label for="file" class="text-sm leading-none font-medium">{m.pdf_file()}</label>
									<div class="relative">
										<Input
											id="file"
											name="file"
											type="file"
											accept="application/pdf"
											required
											class="sr-only"
											bind:files={manualFiles}
										/>
										<label
											for="file"
											class="border-input hover:bg-accent hover:text-accent-foreground flex h-9 w-full cursor-pointer items-center rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs transition-colors"
										>
											<span class="text-muted-foreground truncate">
												{manualFiles && manualFiles.length > 0
													? manualFiles[0].name
													: m.choose_file()}
											</span>
										</label>
									</div>
								</div>
								<div class="md:basis-full">
									<AiEffortSelect id="upload-effort" user={data.user} allowNone />
								</div>
								<Button type="submit" disabled={uploading}>
									{uploading ? m.adding() : m.add()}
								</Button>
							</form>
						</Tabs.Content>
						<Tabs.Content value="imslp">
							<ImslpSearch
								preferredInstrument={data.user?.instrument}
								onSelect={(work) => {
									if (uploading) return;
									agentSelectedScore = work;
									imslpSheetOpen = true;
								}}
							/>
							<details class="mt-6" open={imslpAgentHistoryStore.history.length > 0}>
								<summary
									class="text-muted-foreground hover:text-foreground cursor-pointer text-sm font-medium"
								>
									{m.imslp_ask_assistant()}
									<AiBadge class="ml-1" />
								</summary>
								<div
									class="mt-3 flex flex-col {imslpAgentHistoryStore.history.length > 0
										? 'h-[500px]'
										: 'h-auto'} w-full"
								>
									<AgentChat
										form={form?.formId === 'agent' ? form : null}
										action="?/ask_agent"
										title={m.imslp_search_help()}
										placeholder={m.agent_placeholder_imslp()}
										onResult={onImslpResult}
										user={data.user}
										store={imslpAgentHistoryStore}
									>
										<div class="max-w-sm text-xs">
											{m.warning_limit_100()}
										</div>
										{#snippet resultSnippet({ msg, isLast })}
											<p class="mb-4 text-sm whitespace-pre-wrap">{msg.answer}</p>
											{#if isLast}
												{#if Array.isArray(msg.scores) && msg.scores.length > 0}
													<div
														class="bg-card text-card-foreground shadow-card mb-4 overflow-hidden rounded-md border"
													>
														<Table.Root>
															<Table.Header>
																{#each imslpTable.getHeaderGroups() as headerGroup (headerGroup.id)}
																	<Table.Row>
																		{#each headerGroup.headers as header (header.id)}
																			<Table.Head>
																				{#if !header.isPlaceholder}
																					<FlexRender {header} />
																				{/if}
																			</Table.Head>
																		{/each}
																	</Table.Row>
																{/each}
															</Table.Header>
															<Table.Body>
																{#each imslpTable.getRowModel().rows as row (row.id)}
																	<Table.Row
																		class="hover:bg-muted/50 cursor-pointer transition-colors {agentSelectedScore?.id ===
																		row.original.id
																			? 'bg-muted'
																			: ''}"
																		onclick={() => {
																			if (!uploading) {
																				agentSelectedScore = row.original;
																				imslpSheetOpen = true;
																			}
																		}}
																	>
																		{#each row.getAllCells() as cell (cell.id)}
																			<Table.Cell
																				class="max-w-[120px] truncate sm:max-w-[150px] md:max-w-[200px]"
																			>
																				<FlexRender {cell} />
																			</Table.Cell>
																		{/each}
																	</Table.Row>
																{/each}
															</Table.Body>
														</Table.Root>

														<div class="flex items-center justify-end space-x-2 border-t px-4 py-4">
															<div class="text-muted-foreground flex-1 text-sm">
																{m.page_of({
																	page: imslpTable.atoms.pagination.get().pageIndex + 1,
																	total: Math.max(1, imslpTable.getPageCount())
																})}
															</div>
															<Button
																variant="outline"
																size="sm"
																onclick={() => imslpTable.previousPage()}
																disabled={!imslpTable.getCanPreviousPage()}
															>
																{m.previous()}
															</Button>
															<Button
																variant="outline"
																size="sm"
																onclick={() => imslpTable.nextPage()}
																disabled={!imslpTable.getCanNextPage()}
															>
																{m.next()}
															</Button>
														</div>
													</div>
												{:else if msg.answer}
													<p class="text-muted-foreground mt-2 text-center text-sm">
														{m.no_matching_scores()}
													</p>
												{/if}
											{/if}
										{/snippet}
									</AgentChat>
								</div>
							</details>
						</Tabs.Content>
					</Tabs.Root>
					<!-- Agent errors are shown by AgentChat itself, under its input. -->
					{#if form?.error && form?.formId !== 'agent'}
						<p role="alert" class="text-destructive mt-4 text-sm font-medium">{form.error}</p>
					{/if}
					{#if form?.scoreAdded}
						<p role="status" class="text-success mt-4 text-sm font-medium">
							{m.score_added_success()}
						</p>
						{#if form?.aiSkipped}
							<p role="status" class="text-muted-foreground mt-1 text-sm">
								{m.score_added_no_ai()}
							</p>
						{/if}
						{#if form?.completionFailed}
							<p role="status" class="text-muted-foreground mt-1 text-sm">
								{m.score_completion_failed()}
								{#if form?.completionError}({form.completionError}){/if}
							</p>
						{/if}
					{/if}
				</div>
			</Tabs.Content>
		{/if}
	</Tabs.Root>
</div>

<ScoreDetailsDialog
	score={selectedScore}
	bind:open={sheetOpen}
	user={data.user}
	onEdit={() => (editOpen = true)}
	onDeleted={() => (selectedScoreId = null)}
/>

<ImslpAddDialog bind:work={agentSelectedScore} bind:open={imslpSheetOpen} />

<EditScoreDialog bind:open={editOpen} score={selectedScore} />
