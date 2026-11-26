<script lang="ts">
	import type { PageProps } from './$types';
	import { resolve } from '$app/paths';
	import { enhance } from '$app/forms';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import * as Table from '#lib/components/ui/table/index.js';
	import ScoreDetailsDialog from '#lib/components/ScoreDetailsDialog.svelte';
	import InfoIcon from '@lucide/svelte/icons/info';
	import * as Tabs from '#lib/components/ui/tabs/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
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
	import type { Score, IMSLPScore, ImslpResult } from '#lib/types.js';
	import ImslpSearch from '#lib/components/ImslpSearch.svelte';
	import ImslpAddDialog from '#lib/components/ImslpAddDialog.svelte';
	import AgentChat from '#lib/components/AgentChat.svelte';
	import EditScoreDialog from '#lib/components/EditScoreDialog.svelte';
	import DataTableSortButton from './data-table-sort-button.svelte';
	import { imslpAgentHistoryStore } from '#lib/stores/chat.svelte.js';
	import * as m from '#lib/paraglide/messages.js';
	import { aiLeftLabel, formatBytes } from '#lib/usage.js';

	let { data, form }: PageProps = $props();
	let selectedScoreId = $state<number | null>(null);
	let agentSelectedScore = $state<IMSLPScore | ImslpResult | null>(null);
	let imslpSheetOpen = $state(false);
	let uploading = $state(false);
	let sheetOpen = $state(false);
	let editOpen = $state(false);
	let manualFiles = $state<FileList | undefined>();
	let selectedScore = $derived(data.scores.find((s: Score) => s.id === selectedScoreId));

	function openDetails(id: number) {
		selectedScoreId = id;
		sheetOpen = true;
	}

	let pagination = $state<PaginationState>({ pageIndex: 0, pageSize: 10 });
	let sorting = $state<SortingState>([]);
	let columnFilters = $state<ColumnFiltersState>([]);

	const columns: ColumnDef<Score>[] = [
		{
			accessorKey: 'title',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.label_title(),
					onclick: column.getToggleSortingHandler()
				})
		},
		{
			accessorKey: 'composer',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.label_composer(),
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
			filterFn: (row, columnId, filterValue) => {
				const val = row.getValue(columnId) as number;
				const [min, max] = (filterValue as [number | undefined, number | undefined]) || [
					undefined,
					undefined
				];
				if (min !== undefined && !isNaN(min) && val < min) return false;
				if (max !== undefined && !isNaN(max) && val > max) return false;
				return true;
			}
		},
		{ accessorKey: 'period', header: m.label_period() },
		{ accessorKey: 'genre', header: m.label_genre() },
		{
			accessorKey: 'number_of_plays',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.home_stat_plays(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) => row.original.number_of_plays ?? 0
		},
		{
			id: 'pdf_size',
			accessorFn: (score) => score.pdf_size ?? 0,
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.label_size(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) => (row.original.pdf_size ? formatBytes(row.original.pdf_size) : '-')
		}
	];

	const table = createSvelteTable({
		get data() {
			return data.scores;
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
			if (typeof updater === 'function') {
				pagination = updater(pagination);
			} else {
				pagination = updater;
			}
		},
		onSortingChange: (updater) => {
			if (typeof updater === 'function') {
				sorting = updater(sorting);
			} else {
				sorting = updater;
			}
		},
		onColumnFiltersChange: (updater) => {
			if (typeof updater === 'function') {
				columnFilters = updater(columnFilters);
			} else {
				columnFilters = updater;
			}
		},
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getFilteredRowModel: getFilteredRowModel()
	});

	let imslpPagination = $state<PaginationState>({ pageIndex: 0, pageSize: 5 });
	let imslpSorting = $state<SortingState>([]);
	let imslpColumnFilters = $state<ColumnFiltersState>([]);

	const imslpColumns: ColumnDef<IMSLPScore>[] = [
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

	const imslpTable = createSvelteTable({
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
		},
		onColumnFiltersChange: (updater) => {
			if (typeof updater === 'function') {
				imslpColumnFilters = updater(imslpColumnFilters);
			} else {
				imslpColumnFilters = updater;
			}
		},
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(),
		getSortedRowModel: getSortedRowModel(),
		getFilteredRowModel: getFilteredRowModel()
	});
</script>

<div class="p-8">
	{#if !page.data.isDemo}
		<div class="bg-card text-card-foreground shadow-card mb-8 rounded-md border p-4">
			<div class="mb-4 flex items-center justify-between gap-2">
				<h2 class="text-fancy-title text-lg font-semibold">{m.add_new_score()}</h2>
				{#if aiLeftLabel(data.user)}
					<span class="text-muted-foreground text-sm font-medium">{aiLeftLabel(data.user)}</span>
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
						class="flex flex-col gap-4 md:flex-row md:items-end"
					>
						<div class="flex-1 space-y-2">
							<label for="title" class="text-sm leading-none font-medium">{m.title()}</label>
							<Input id="title" name="title" required />
						</div>
						<div class="flex-1 space-y-2">
							<label for="composer" class="text-sm leading-none font-medium">{m.composer()}</label>
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
										{manualFiles && manualFiles.length > 0 ? manualFiles[0].name : m.choose_file()}
									</span>
								</label>
							</div>
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
							>{m.imslp_ask_assistant()}</summary
						>
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
																{#each row.getVisibleCells() as cell (cell.id)}
																	<Table.Cell
																		class="max-w-[120px] truncate sm:max-w-[150px] md:max-w-[200px]"
																	>
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

												<div class="flex items-center justify-end space-x-2 border-t px-4 py-4">
													<div class="text-muted-foreground flex-1 text-sm">
														{m.page_of({
															page: imslpTable.getState().pagination.pageIndex + 1,
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
				{#if form?.completionFailed}
					<p role="status" class="text-muted-foreground mt-1 text-sm">
						{m.score_completion_failed()}
						{#if form?.completionError}({form.completionError}){/if}
					</p>
				{/if}
			{/if}
		</div>
	{/if}

	<div class="mb-4 flex items-center justify-between">
		<h1 class="text-fancy-title text-foreground text-2xl font-bold">{m.database_viewer()}</h1>
		{#if selectedScoreId}
			<div class="flex gap-2">
				{#if !page.data.isDemo}
					<form
						method="POST"
						action="?/delete"
						use:enhance={() => {
							return async ({ update, result }) => {
								if (result.type === 'success') {
									selectedScoreId = null;
								}
								update();
							};
						}}
					>
						<input type="hidden" name="id" value={selectedScoreId} />
						<Button type="submit" variant="destructive">{m.delete()}</Button>
					</form>
				{/if}
				<Button href={resolve('/reader/[id]', { id: String(selectedScoreId) })}
					>{m.view_pdf()}</Button
				>
			</div>
		{/if}
	</div>

	<div class="flex flex-wrap items-center gap-4 py-4">
		<Input
			placeholder={m.filter_titles()}
			value={(table.getColumn('title')?.getFilterValue() as string) ?? ''}
			oninput={(e) => table.getColumn('title')?.setFilterValue(e.currentTarget.value)}
			class="max-w-xs"
		/>
		<Input
			placeholder={m.filter_composers()}
			value={(table.getColumn('composer')?.getFilterValue() as string) ?? ''}
			oninput={(e) => table.getColumn('composer')?.setFilterValue(e.currentTarget.value)}
			class="max-w-xs"
		/>
		<Input
			placeholder={m.filter_instrumentation()}
			value={(table.getColumn('instrumentation')?.getFilterValue() as string) ?? ''}
			oninput={(e) => table.getColumn('instrumentation')?.setFilterValue(e.currentTarget.value)}
			class="max-w-xs"
		/>
		<div class="flex items-center gap-2">
			<span class="text-sm font-medium">{m.year()}</span>
			<Input
				type="number"
				placeholder={m.min()}
				value={(table.getColumn('year')?.getFilterValue() as [number, number])?.[0] ?? ''}
				oninput={(e) => {
					const current = (table.getColumn('year')?.getFilterValue() as [
						number | undefined,
						number | undefined
					]) || [undefined, undefined];
					const val = e.currentTarget.value ? parseInt(e.currentTarget.value, 10) : undefined;
					table.getColumn('year')?.setFilterValue([val, current[1]]);
				}}
				class="w-20"
			/>
			<span>-</span>
			<Input
				type="number"
				placeholder={m.max()}
				value={(table.getColumn('year')?.getFilterValue() as [number, number])?.[1] ?? ''}
				oninput={(e) => {
					const current = (table.getColumn('year')?.getFilterValue() as [
						number | undefined,
						number | undefined
					]) || [undefined, undefined];
					const val = e.currentTarget.value ? parseInt(e.currentTarget.value, 10) : undefined;
					table.getColumn('year')?.setFilterValue([current[0], val]);
				}}
				class="w-20"
			/>
		</div>
	</div>

	<div class="bg-card text-card-foreground shadow-card rounded-md border">
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
						<Table.Head><span class="sr-only">{m.view_details()}</span></Table.Head>
					</Table.Row>
				{/each}
			</Table.Header>
			<Table.Body>
				{#each table.getRowModel().rows as row (row.id)}
					<Table.Row
						class="hover:bg-muted/50 cursor-pointer transition-colors {selectedScoreId ===
						row.original.id
							? 'bg-muted'
							: ''}"
						onclick={() => goto(resolve('/reader/[id]', { id: String(row.original.id) }))}
					>
						{#each row.getVisibleCells() as cell (cell.id)}
							<Table.Cell class="max-w-[120px] truncate sm:max-w-[150px] md:max-w-[200px]">
								<FlexRender content={cell.column.columnDef.cell} context={cell.getContext()} />
							</Table.Cell>
						{/each}
						<Table.Cell class="w-0 py-1 text-right">
							<!-- The row opens the score; this opens its details instead. -->
							<Button
								variant="ghost"
								size="icon"
								aria-label={m.view_details()}
								title={m.view_details()}
								onclick={(e: MouseEvent) => {
									e.stopPropagation();
									openDetails(row.original.id);
								}}
							>
								<InfoIcon class="size-4" />
							</Button>
						</Table.Cell>
					</Table.Row>
				{:else}
					<Table.Row>
						<Table.Cell colspan={columns.length + 1} class="text-muted-foreground py-4 text-center">
							{m.no_scores_found()}
						</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>

	<div class="flex items-center justify-end space-x-2 py-4">
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

<ScoreDetailsDialog
	score={selectedScore}
	bind:open={sheetOpen}
	user={data.user}
	onEdit={() => (editOpen = true)}
	onDeleted={() => (selectedScoreId = null)}
/>

<ImslpAddDialog bind:work={agentSelectedScore} bind:open={imslpSheetOpen} />

<EditScoreDialog bind:open={editOpen} score={selectedScore} />
