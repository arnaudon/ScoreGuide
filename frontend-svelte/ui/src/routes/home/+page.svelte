<script lang="ts">
	import { resolve } from '$app/paths';
	import * as Table from '#lib/components/ui/table/index.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import ScoreDetails from '#lib/components/ScoreDetails.svelte';
	import AgentChat from '#lib/components/AgentChat.svelte';
	import ImslpSearch from '#lib/components/ImslpSearch.svelte';
	import ImslpAddDialog from '#lib/components/ImslpAddDialog.svelte';
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

<div class="mx-auto flex h-[calc(100vh-12rem)] w-full max-w-4xl flex-col">
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
	{#if !data.isDemo}
		<section
			class="bg-card shadow-card mb-4 flex shrink-0 flex-col gap-2 rounded-md border p-4"
			aria-labelledby="imslp-home-title"
		>
			<h2 id="imslp-home-title" class="text-foreground font-semibold">{m.imslp_home_title()}</h2>
			<p class="text-muted-foreground text-sm">{m.imslp_home_desc()}</p>
			<ImslpSearch
				preferredInstrument={data.user.instrument}
				listClass="max-h-64 overflow-y-auto"
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
	<AgentChat
		{form}
		action="?/ask"
		title={m.hello_user({ name: data.user.username })}
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
