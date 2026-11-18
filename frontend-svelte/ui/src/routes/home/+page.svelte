<script lang="ts">
	import { resolve } from '$app/paths';
	import * as Table from '#lib/components/ui/table/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import ScoreDetails from '#lib/components/ScoreDetails.svelte';
	import AgentChat from '#lib/components/AgentChat.svelte';
	import ImslpSearch from '#lib/components/ImslpSearch.svelte';
	import ImslpAddDialog from '#lib/components/ImslpAddDialog.svelte';
	import BookOpenIcon from '@lucide/svelte/icons/book-open';
	import { composerName, summarizeLibrary } from '#lib/library.js';
	import { periodLabel } from '#lib/imslp.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { mainAgentHistoryStore } from '#lib/stores/chat.svelte.js';
	import {
		type ColumnDef,
		type PaginationState,
		type SortingState,
		type ColumnFiltersState,
		getCoreRowModel,
		getPaginationRowModel,
		getSortedRowModel,
		getFilteredRowModel
	} from '@tanstack/table-core';
	import {
		FlexRender,
		createSvelteTable,
		renderComponent
	} from '#lib/components/ui/data-table/index.js';
	import DataTableSortButton from '../db-viewer/data-table-sort-button.svelte';
	import type { ImslpResult, Score } from '#lib/types.js';
	import * as m from '#lib/paraglide/messages.js';

	let { form, data } = $props();
	let sheetOpen = $state(false);
	let selectedScoreDetails = $state<Score | null>(null);
	let imslpWork = $state<ImslpResult | null>(null);
	let imslpOpen = $state(false);
	let addedScoreId = $state<number | null | undefined>(undefined);
	let summary = $derived(summarizeLibrary(data.scores ?? []));
	let composerMax = $derived(Math.max(1, ...summary.topComposers.map((c) => c.count)));
	let periodMax = $derived(Math.max(1, ...summary.periods.map((p) => p.count)));

	let pagination = $state<PaginationState>({ pageIndex: 0, pageSize: 5 });
	let sorting = $state<SortingState>([]);
	let columnFilters = $state<ColumnFiltersState>([]);
	let currentScores = $state<Score[]>([]);

	const columns: ColumnDef<Score>[] = [
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

	const table = createSvelteTable({
		get data() {
			return currentScores;
		},
		columns,
		state: {
			get pagination() {
				return pagination;
			},
			get sorting() {
				return sorting;
			},
			get columnFilters() {
				return columnFilters;
			}
		},
		onPaginationChange: (updater) => {
			if (typeof updater === 'function') pagination = updater(pagination);
			else pagination = updater;
		},
		onSortingChange: (updater) => {
			if (typeof updater === 'function') sorting = updater(sorting);
			else sorting = updater;
		},
		onColumnFiltersChange: (updater) => {
			if (typeof updater === 'function') columnFilters = updater(columnFilters);
			else columnFilters = updater;
		},
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getFilteredRowModel: getFilteredRowModel()
	});

	function onResult(data: Record<string, unknown>) {
		const answer = (data.answer ?? {}) as Record<string, unknown>;
		const inner = (answer.response ?? null) as Record<string, unknown> | string | null;
		let textAns: unknown =
			typeof inner === 'object' && inner !== null && 'response' in inner ? inner.response : inner;

		const scoreId = answer.score_id ?? (typeof inner === 'object' && inner ? inner.score_id : null);
		const scores = (data.scores as Score[] | undefined) ?? [];
		currentScores = scores;

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

			<a href={resolve('db-viewer')} class="text-primary font-medium hover:underline"
				>{m.empty_db_link()}</a
			>

			{m.empty_db_p2()}
		</div>
	{/if}
	<!-- While a conversation is open the chat gets a fixed height and scrolls inside. -->
	<div class="flex flex-col {mainAgentHistoryStore.history.length ? 'h-[70vh] min-h-96' : 'py-4'}">
		<AgentChat
			{form}
			action="?/ask"
			title={m.hello_user({ name: data.user.username })}
			titleClass="text-fancy-title text-3xl leading-tight font-semibold sm:text-4xl"
			emptyMessage={m.what_to_play()}
			placeholder={m.agent_placeholder_main()}
			{onResult}
			user={data.user}
			store={mainAgentHistoryStore}
		>
			{#snippet resultSnippet({ msg, isLast })}
				<p class="text-muted-foreground mt-2 whitespace-pre-wrap">{msg.answer}</p>
				{#if isLast && Array.isArray(msg.scores) && msg.scores.length > 0}
					<div
						class="bg-card text-card-foreground shadow-card mt-4 overflow-hidden rounded-md border"
					>
						<Table.Root>
							<Table.Header>
								{#each table.getHeaderGroups() as headerGroup (headerGroup.id)}
									<Table.Row>
										{#each headerGroup.headers as header (header.id)}
											<Table.Head>
												{#if !header.isPlaceholder}
													<FlexRender
														content={header.column.columnDef.header}
														context={header.getContext()}
													/>
												{/if}
											</Table.Head>
										{/each}
									</Table.Row>
								{/each}
							</Table.Header>
							<Table.Body>
								{#each table.getRowModel().rows as row (row.id)}
									<Table.Row
										class="hover:bg-muted/50 cursor-pointer transition-colors {selectedScoreDetails?.id ===
										row.original.id
											? 'bg-muted'
											: ''}"
										onclick={() => {
											selectedScoreDetails = row.original;
											sheetOpen = true;
										}}
									>
										{#each row.getVisibleCells() as cell (cell.id)}
											<Table.Cell class="max-w-[120px] truncate sm:max-w-[150px] md:max-w-[200px]">
												<FlexRender
													content={cell.column.columnDef.cell}
													context={cell.getContext()}
												/>
											</Table.Cell>
										{/each}
									</Table.Row>
								{/each}
							</Table.Body>
						</Table.Root>

						<div class="border-border flex items-center justify-end space-x-2 border-t px-4 py-4">
							<div class="text-muted-foreground flex-1 text-sm">
								{m.page_of({
									page: table.getState().pagination.pageIndex + 1,
									total: Math.max(1, table.getPageCount())
								})}
							</div>
							<Button
								variant="outline"
								size="sm"
								onclick={() => table.previousPage()}
								disabled={!table.getCanPreviousPage()}
							>
								{m.previous()}
							</Button>
							<Button
								variant="outline"
								size="sm"
								onclick={() => table.nextPage()}
								disabled={!table.getCanNextPage()}
							>
								{m.next()}
							</Button>
						</div>
					</div>
				{/if}
				{#if msg.score_id}
					<div class="mt-4">
						<Button
							variant="secondary"
							size="sm"
							href={resolve('/reader/[id]', { id: String(msg.score_id) })}
						>
							{m.view_pdf()} (ID: {msg.score_id})
						</Button>
					</div>
				{/if}
			{/snippet}
		</AgentChat>
	</div>
	{#if summary.total}
		<section aria-labelledby="home-continue" class="flex flex-col gap-3">
			<div class="flex items-baseline justify-between gap-4">
				<h2 id="home-continue" class="text-fancy-title text-foreground text-2xl font-semibold">
					{summary.continueIsRecent ? m.home_recent() : m.home_continue()}
				</h2>
				<a href={resolve('/db-viewer')} class="text-primary text-sm font-medium hover:underline"
					>{m.home_see_library()}</a
				>
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
								>{composerName(score.composer)}</span
							>
							<span
								class="text-fancy-title text-foreground group-hover:text-primary line-clamp-3 text-base leading-snug font-semibold sm:text-lg"
								>{score.title}</span
							>
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
					<div class="bg-card shadow-card flex flex-col-reverse rounded-lg border p-4">
						<dt class="text-muted-foreground text-xs font-medium sm:text-sm">{stat.label}</dt>
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
										class="text-foreground hover:text-primary truncate">{score.title}</a
									>
									<span class="text-muted-foreground shrink-0 tabular-nums"
										>{m.home_played_times({ count: score.number_of_plays })}</span
									>
								</li>
							{/each}
						</ol>
					{/if}
				</div>
			</div>
		</section>
	{/if}

	{#if !data.isDemo}
		<section
			class="bg-card shadow-card flex shrink-0 flex-col gap-2 rounded-md border p-4"
			aria-labelledby="imslp-home-title"
		>
			<h2 id="imslp-home-title" class="text-foreground font-semibold">{m.imslp_home_title()}</h2>
			<p class="text-muted-foreground text-sm">{m.imslp_home_desc()}</p>
			<ImslpSearch
				preferredInstrument={data.user.instrument}
				listClass="max-h-48 overflow-y-auto"
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
							class="text-primary font-medium hover:underline">{m.imslp_open_added()}</a
						>
					{/if}
				</p>
			{/if}
		</section>
	{/if}
</div>

<Dialog.Root bind:open={sheetOpen}>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title class="text-fancy-title text-2xl"
				>{selectedScoreDetails?.title || m.score_details()}</Dialog.Title
			>
			<Dialog.Description
				>{selectedScoreDetails?.composer || m.score_details_desc()}</Dialog.Description
			>
		</Dialog.Header>
		{#if selectedScoreDetails}
			<ScoreDetails score={selectedScoreDetails} />

			<div class="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
				<Button
					href={resolve('/reader/[id]', { id: String(selectedScoreDetails.id) })}
					class="w-full">{m.view_pdf()}</Button
				>
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>

<ImslpAddDialog
	bind:work={imslpWork}
	bind:open={imslpOpen}
	action="/db-viewer?/add_imslp"
	onAdded={(id) => (addedScoreId = id)}
/>
