<script lang="ts">
	import type { PageProps } from './$types';
	import * as Table from '$lib/components/ui/table/index.js';
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import { Button } from '$lib/components/ui/button/index.js';
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
	} from '$lib/components/ui/data-table/index.js';
	import DataTableSortButton from '../db-viewer/data-table-sort-button.svelte';
	import EditCreditsDialog from './EditCreditsDialog.svelte';
	import type { AdminUser } from '$lib/types.js';
	import * as m from '$lib/paraglide/messages.js';

	let { data, form }: PageProps = $props();

	let selectedUser = $state<AdminUser | null>(null);
	let editDialogOpen = $state(false);
	let savingModels = $state(false);

	// The model dropdowns intentionally accept any pydantic-ai model string
	// (the backend doesn't restrict it — see backend/app/main.py's
	// set_active_model), so this list is just the common presets, not a
	// whitelist. If the DB is already set to something outside this list
	// (e.g. changed via a migration or direct DB edit), we inject it as an
	// extra option below instead of silently dropping the select back to
	// the first preset — otherwise hitting Save without touching the
	// dropdown would silently overwrite a working setting.
	const MODEL_PRESETS = [
		{ value: 'google:gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash Lite' },
		{ value: 'google:gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
		{ value: 'google:gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
		{ value: 'google:gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro Preview' }
	];
	const DEFAULT_MODEL = 'google:gemini-2.5-flash';

	function optionsFor(current: string) {
		if (current && !MODEL_PRESETS.some((o) => o.value === current)) {
			return [...MODEL_PRESETS, { value: current, label: current }];
		}
		return MODEL_PRESETS;
	}

	function isSelected(current: string, value: string) {
		return current === value || (!current && value === DEFAULT_MODEL);
	}

	function openEditDialog(user: AdminUser) {
		selectedUser = user;
		editDialogOpen = true;
	}

	let pagination = $state<PaginationState>({ pageIndex: 0, pageSize: 10 });
	let sorting = $state<SortingState>([]);
	let columnFilters = $state<ColumnFiltersState>([]);

	const columns: ColumnDef<AdminUser>[] = [
		{
			accessorKey: 'id',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.id(),
					onclick: column.getToggleSortingHandler()
				})
		},
		{
			accessorKey: 'username',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.username(),
					onclick: column.getToggleSortingHandler()
				})
		},
		{
			accessorKey: 'email',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.email(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) => row.original.email || '-'
		},
		{
			accessorKey: 'instrument',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.preferred_instrument(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) => row.original.instrument || '-'
		},
		{
			accessorKey: 'role',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.role(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) =>
				row.original.role === 'admin' ? m.admin_role_admin() : m.admin_role_user()
		},
		{
			accessorKey: 'credits',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.credits(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) => `${row.original.credits ?? '-'}/${row.original.max_credits ?? '-'}`
		},
		{
			accessorKey: 'score_count',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.admin_scores(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) => row.original.score_count ?? 0
		},
		{
			accessorKey: 'last_login',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.admin_last_login(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) =>
				row.original.last_login ? new Date(row.original.last_login).toLocaleString() : '-'
		}
	];

	const table = createSvelteTable({
		get data() {
			return data.users;
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

	$effect(() => {
		if (data.progress?.status === 'processing' || data.progress?.status === 'cancelling') {
			const interval = setInterval(() => {
				invalidateAll();
			}, 2000);
			return () => clearInterval(interval);
		}
	});
</script>

<div class="mb-4 flex items-center justify-between">
	<h1 class="text-fancy-title text-foreground text-2xl font-bold">{m.admin_dashboard()}</h1>
</div>

<div class="mb-8 grid gap-6 md:grid-cols-2">
	<div class="bg-card text-card-foreground shadow-card rounded-md border p-6">
		<h2 class="text-fancy-title mb-2 text-xl font-semibold">{m.agent_configuration()}</h2>
		<p class="text-muted-foreground mb-4">{m.agent_configuration_desc()}</p>
		{#snippet modelSelect(idName: string, label: string, current: string)}
			<div class="space-y-2">
				<label for={idName} class="text-sm leading-none font-medium">{label}</label>
				<select
					id={idName}
					name={idName}
					class="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus:ring-ring flex h-10 w-full items-center justify-between rounded-md border px-3 py-2 text-sm focus:ring-2 focus:ring-offset-2 focus:outline-none"
				>
					{#each optionsFor(current) as opt (opt.value)}
						<option value={opt.value} selected={isSelected(current, opt.value)}>{opt.label}</option>
					{/each}
				</select>
			</div>
		{/snippet}
		<form
			method="POST"
			action="?/set_models"
			class="flex flex-col gap-4"
			use:enhance={() => {
				savingModels = true;
				return async ({ update }) => {
					savingModels = false;
					await update();
				};
			}}
		>
			{@render modelSelect('model_main', m.main_agent_model(), data.activeModels.main)}
			{@render modelSelect('model_imslp', m.imslp_agent_model(), data.activeModels.imslp)}
			{@render modelSelect('model_complete', m.complete_agent_model(), data.activeModels.complete)}
			{@render modelSelect(
				'model_imslp_complete',
				m.imslp_complete_agent_model(),
				data.activeModels.imslp_complete
			)}
			{#if form?.formId === 'models' && form?.error}
				<p role="alert" class="text-destructive text-sm font-medium">{form.error}</p>
			{/if}
			{#if form?.formId === 'models' && form?.success}
				<p role="status" class="text-sm font-medium text-green-600 dark:text-green-400">
					{m.models_updated_success()}
				</p>
			{/if}
			<button
				class="ring-offset-background focus-visible:ring-ring bg-primary text-primary-foreground hover:bg-primary/90 inline-flex h-10 items-center justify-center self-start rounded-md px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
				type="submit"
				disabled={savingModels}
			>
				{savingModels ? m.saving() : m.save()}
			</button>
		</form>
	</div>

	<div class="bg-card text-card-foreground shadow-card rounded-md border p-6">
		<h2 class="text-fancy-title mb-2 text-xl font-semibold">{m.imslp_database()}</h2>
		<p class="text-muted-foreground mb-4">
			{m.imslp_database_stats({
				works: data.stats?.total_works || 0,
				composers: data.stats?.total_composers || 0
			})}
		</p>
		<div class="flex items-center gap-4">
			<form method="POST" action="?/update" use:enhance>
				<button
					class="ring-offset-background focus-visible:ring-ring bg-primary text-primary-foreground hover:bg-primary/90 inline-flex h-10 items-center justify-center rounded-md px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
					disabled={data.progress?.status === 'processing'}
				>
					{m.update_database()}
				</button>
			</form>
			<form
				method="POST"
				action="?/empty"
				use:enhance
				onsubmit={(e) => {
					if (!confirm(m.delete_imslp_confirm())) e.preventDefault();
				}}
			>
				<button
					class="ring-offset-background focus-visible:ring-ring bg-destructive text-destructive-foreground hover:bg-destructive/90 inline-flex h-10 items-center justify-center rounded-md px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
					disabled={data.progress?.status === 'processing'}
				>
					{m.delete_all_data()}
				</button>
			</form>
		</div>

		{#if data.progress?.status === 'processing' || data.progress?.status === 'cancelling'}
			<div class="bg-muted/50 mt-6 rounded-md border p-4">
				<div class="mb-2 flex justify-between">
					<span class="text-sm font-medium">
						{#if data.progress.status === 'cancelling'}
							{m.status_cancelling()}
						{:else}
							{m.status_processing({ page: data.progress.page, total: data.progress.total })}
						{/if}
					</span>
				</div>
				<div class="bg-secondary mb-4 h-2.5 w-full overflow-hidden rounded-full">
					<div
						class="bg-primary h-2.5 rounded-full transition-all"
						style="width: {(data.progress.page / Math.max(1, data.progress.total)) * 100}%"
					></div>
				</div>
				<form method="POST" action="?/cancel" use:enhance>
					<button
						disabled={data.progress.status === 'cancelling'}
						class="ring-offset-background focus-visible:ring-ring border-input bg-background hover:bg-accent hover:text-accent-foreground inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-50"
					>
						{data.progress.status === 'cancelling' ? m.cancelling() : m.cancel_task()}
					</button>
				</form>
			</div>
		{/if}
	</div>
</div>

<div class="mb-4 flex items-center justify-between">
	<h2 class="text-fancy-title text-foreground text-xl font-semibold">{m.users()}</h2>
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
					<Table.Head class="text-right">{m.actions()}</Table.Head>
				</Table.Row>
			{/each}
		</Table.Header>
		<Table.Body>
			{#each table.getRowModel().rows as row (row.id)}
				<Table.Row class="hover:bg-muted/50 transition-colors">
					{#each row.getVisibleCells() as cell (cell.id)}
						<Table.Cell>
							<FlexRender content={cell.column.columnDef.cell} context={cell.getContext()} />
						</Table.Cell>
					{/each}
					<Table.Cell class="text-right">
						<div class="flex items-center justify-end gap-2">
							<Button variant="outline" size="sm" onclick={() => openEditDialog(row.original)}
								>{m.edit()}</Button
							>
						</div>
					</Table.Cell>
				</Table.Row>
			{:else}
				<Table.Row>
					<Table.Cell colspan={columns.length + 1} class="text-muted-foreground py-4 text-center">
						{m.no_users_found()}
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

<EditCreditsDialog bind:open={editDialogOpen} user={selectedUser} />
