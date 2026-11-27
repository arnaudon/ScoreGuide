<script lang="ts">
	import type { PageProps } from './$types';
	import * as Table from '#lib/components/ui/table/index.js';
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
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
	import DataTableSortButton from '../db-viewer/data-table-sort-button.svelte';
	import EditPlanDialog from './EditPlanDialog.svelte';
	import type { AdminUser, UsageRow } from '#lib/types.js';
	import { aiUsedPercent, formatBytes, planLabel } from '#lib/usage.js';
	import { formatWeights } from '#lib/modelWeights.js';
	import * as m from '#lib/paraglide/messages.js';

	let { data, form }: PageProps = $props();

	let selectedUser = $state<AdminUser | null>(null);
	let editDialogOpen = $state(false);
	let savingModels = $state(false);
	let savingPlans = $state(false);

	/** AI tokens used / received and storage per user, for the users table. */
	const usageByUser = $derived(
		new Map<number, UsageRow>(data.usageNow.map((row: UsageRow) => [row.user_id, row]))
	);
	const nf = new Intl.NumberFormat();

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
		{ value: 'google:gemini-3.1-pro-preview', label: 'Gemini 3.1 Pro Preview' },
		// Infomaniak AI Services (open models hosted in Switzerland); check the
		// exact model names in the Infomaniak Manager.
		{ value: 'infomaniak:Qwen/Qwen3.5-397B-A17B-FP8', label: 'Infomaniak · Qwen 3.5 397B' },
		{ value: 'infomaniak:moonshotai/Kimi-K2.6', label: 'Infomaniak · Kimi K2.6' },
		{
			value: 'infomaniak:mistralai/Mistral-Small-4-119B-2603',
			label: 'Infomaniak · Mistral Small 4'
		},
		{ value: 'infomaniak:google/gemma-4-31B-it', label: 'Infomaniak · Gemma 4 31B' },
		{ value: 'infomaniak:swiss-ai/Apertus-v1.5-70B', label: 'Infomaniak · Apertus 70B' },
		{ value: 'infomaniak:Qwen/Qwen3.8-27B-FP8', label: 'Infomaniak · Qwen 3.8 27B' },
		{
			value: 'infomaniak:mistralai/Ministral-3-14B-Instruct-2512',
			label: 'Infomaniak · Ministral 14B (smallest)'
		}
	];

	const CREDENTIAL_FIELDS = [
		{ name: 'google_api_key', label: () => m.credential_google_api_key(), secret: true },
		{ name: 'infomaniak_api_key', label: () => m.credential_infomaniak_api_key(), secret: true },
		{
			name: 'infomaniak_product_id',
			label: () => m.credential_infomaniak_product_id(),
			secret: false
		}
	] as const;
	let savingCredentials = $state(false);

	function credentialState(name: (typeof CREDENTIAL_FIELDS)[number]['name']) {
		const status = data.credentials?.[name];
		if (!status?.set) return m.credential_not_set();
		return status.source === 'admin'
			? m.credential_set_admin({ hint: status.hint })
			: m.credential_set_env({ hint: status.hint });
	}
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
			accessorKey: 'plan',
			header: ({ column }) =>
				renderComponent(DataTableSortButton, {
					title: m.admin_plan(),
					onclick: column.getToggleSortingHandler()
				}),
			cell: ({ row }) => planLabel(row.original.plan)
		},
		{
			id: 'ai_used',
			header: () => m.admin_ai_month(),
			cell: ({ row }) => {
				const usage = usageByUser.get(row.original.id);
				if (!usage) return '-';
				return `${aiUsedPercent(usage)}% (${nf.format(usage.ai_used)} / ${nf.format(usage.ai_allowance)})`;
			}
		},
		{
			id: 'storage',
			header: () => m.admin_storage(),
			cell: ({ row }) => {
				const usage = usageByUser.get(row.original.id);
				return usage
					? `${formatBytes(usage.storage_used)} / ${formatBytes(usage.storage_limit)}`
					: '-';
			}
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

	// The sync runs for hours: refresh its progress while it runs here.
	let syncing = $derived(Boolean(data.progress?.running));
	let resumable = $derived(
		['cancelled', 'error', 'running'].includes(data.progress?.status ?? '') && !syncing
	);
	$effect(() => {
		if (syncing) {
			const interval = setInterval(() => invalidateAll(), 5000);
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
					// Don't reset: form.reset() restores the server-rendered defaults,
					// leaving selects showing values that aren't in the DB, which the
					// next Save would then write back.
					await update({ reset: false });
				};
			}}
		>
			{@render modelSelect('model_main', m.main_agent_model(), data.activeModels.main)}
			{@render modelSelect('model_imslp', m.imslp_agent_model(), data.activeModels.imslp)}
			{@render modelSelect('model_complete', m.complete_agent_model(), data.activeModels.complete)}
			{#if form?.formId === 'models' && form?.error}
				<p role="alert" class="text-destructive text-sm font-medium">{form.error}</p>
			{/if}
			{#if form?.formId === 'models' && form?.success}
				<p role="status" class="text-success text-sm font-medium">
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
		<h2 class="text-fancy-title mb-2 text-xl font-semibold">{m.ai_providers()}</h2>
		<p class="text-muted-foreground mb-4 text-sm">{m.ai_providers_desc()}</p>
		<form
			method="POST"
			action="?/set_credentials"
			class="flex flex-col gap-4"
			autocomplete="off"
			use:enhance={() => {
				savingCredentials = true;
				return async ({ update }) => {
					savingCredentials = false;
					await update();
				};
			}}
		>
			{#each CREDENTIAL_FIELDS as field (field.name)}
				<div class="space-y-2">
					<div class="flex items-baseline justify-between gap-3">
						<label for={field.name} class="text-sm leading-none font-medium">{field.label()}</label>
						<span
							class="text-xs {data.credentials?.[field.name]?.set
								? 'text-success'
								: 'text-muted-foreground'}"
						>
							{credentialState(field.name)}
						</span>
					</div>
					<input
						id={field.name}
						name={field.name}
						type={field.secret ? 'password' : 'text'}
						autocomplete="off"
						spellcheck="false"
						placeholder={data.credentials?.[field.name]?.set
							? m.credential_keep_placeholder()
							: m.credential_new_placeholder()}
						class="border-input bg-background focus:ring-ring flex h-10 w-full rounded-md border px-3 py-2 font-mono text-sm focus:ring-2 focus:outline-none"
					/>
					{#if data.credentials?.[field.name]?.source === 'admin'}
						<label class="text-muted-foreground flex items-center gap-2 text-xs">
							<input type="checkbox" name="clear_{field.name}" />
							{m.credential_clear()}
						</label>
					{/if}
				</div>
			{/each}
			{#if form?.formId === 'credentials' && form?.error}
				<p role="alert" class="text-destructive text-sm font-medium">{form.error}</p>
			{/if}
			{#if form?.formId === 'credentials' && form?.success}
				<p role="status" class="text-success text-sm font-medium">{m.credentials_saved()}</p>
			{/if}
			<button
				class="ring-offset-background focus-visible:ring-ring bg-primary text-primary-foreground hover:bg-primary/90 inline-flex h-10 items-center justify-center self-start rounded-md px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
				type="submit"
				disabled={savingCredentials}
			>
				{savingCredentials ? m.saving() : m.save()}
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
		<p class="text-muted-foreground mb-4 text-sm">{m.imslp_sync_desc()}</p>

		{#if data.progress && data.progress.status !== 'idle'}
			<div class="bg-muted/50 mb-4 rounded-md border p-3 text-sm" role="status">
				{#if data.progress.status === 'completed'}
					{m.imslp_sync_completed({
						works: data.progress.works,
						removed: data.progress.removed ?? 0
					})}
				{:else if data.progress.status === 'error'}
					<span class="text-destructive">
						{m.imslp_sync_error({ start: data.progress.start, error: data.progress.error })}
					</span>
				{:else if syncing}
					{m.imslp_sync_running({ works: data.progress.works, start: data.progress.start })}
				{:else}
					{m.imslp_sync_cancelled({ works: data.progress.works, start: data.progress.start })}
				{/if}
				{#if data.progress.updated_at}
					<span class="text-muted-foreground block text-xs">
						{m.imslp_sync_updated({
							time: new Date(data.progress.updated_at + 'Z').toLocaleString()
						})}
					</span>
				{/if}
			</div>
		{/if}

		<div class="flex flex-wrap items-center gap-3">
			{#if syncing}
				<form method="POST" action="?/cancel" use:enhance>
					<Button type="submit" variant="outline">{m.imslp_sync_cancel()}</Button>
				</form>
			{:else}
				<form method="POST" action="?/update" use:enhance>
					<Button type="submit">{resumable ? m.imslp_sync_resume() : m.imslp_sync_start()}</Button>
				</form>
				{#if resumable}
					<form method="POST" action="?/update" use:enhance>
						<input type="hidden" name="restart" value="true" />
						<Button type="submit" variant="outline">{m.imslp_sync_restart()}</Button>
					</form>
				{/if}
				<form
					method="POST"
					action="?/empty"
					use:enhance
					onsubmit={(e) => {
						if (!confirm(m.delete_imslp_confirm())) e.preventDefault();
					}}
				>
					<Button type="submit" variant="destructive">{m.delete_all_data()}</Button>
				</form>
			{/if}
		</div>

		{#if form?.formId === 'imslp' && form?.error}
			<p role="alert" class="text-destructive mt-4 text-sm font-medium">{form.error}</p>
		{/if}
	</div>
</div>

{#if data.planSettings}
	<section class="bg-card text-card-foreground shadow-card mb-8 rounded-md border p-6">
		<h2 class="text-fancy-title mb-2 text-xl font-semibold">{m.plans_title()}</h2>
		<p class="text-muted-foreground mb-4 text-sm">{m.plans_desc()}</p>
		<form
			method="POST"
			action="?/set_plans"
			class="flex flex-col gap-4"
			use:enhance={() => {
				savingPlans = true;
				return async ({ update }) => {
					savingPlans = false;
					await update({ reset: false });
				};
			}}
		>
			<div class="grid gap-4 sm:grid-cols-2">
				{#each ['free', 'pro'] as const as plan (plan)}
					<fieldset class="space-y-3 rounded-md border p-4">
						<legend class="px-1 text-sm font-semibold">{planLabel(plan)}</legend>
						<div class="space-y-1">
							<label for="{plan}_ai_tokens" class="text-sm font-medium">{m.plan_ai_tokens()}</label>
							<Input
								id="{plan}_ai_tokens"
								name="{plan}_ai_tokens"
								type="number"
								min="0"
								required
								value={data.planSettings.limits[plan].ai_tokens}
							/>
						</div>
						<div class="space-y-1">
							<label for="{plan}_storage_mb" class="text-sm font-medium">
								{m.plan_storage_mb()}
							</label>
							<Input
								id="{plan}_storage_mb"
								name="{plan}_storage_mb"
								type="number"
								min="0"
								required
								value={data.planSettings.limits[plan].storage_mb}
							/>
						</div>
					</fieldset>
				{/each}
			</div>
			<div class="space-y-1">
				<label for="weights" class="text-sm font-medium">{m.model_weights()}</label>
				<p class="text-muted-foreground text-xs">{m.model_weights_desc()}</p>
				<textarea
					id="weights"
					name="weights"
					rows="3"
					placeholder="infomaniak:moonshotai/Kimi-K2.6 = 5"
					class="border-input bg-background focus:ring-ring w-full rounded-md border px-3 py-2 font-mono text-sm focus:ring-2 focus:outline-none"
					>{formatWeights(data.planSettings.weights)}</textarea
				>
			</div>
			{#if form?.formId === 'plans' && form?.error}
				<p role="alert" class="text-destructive text-sm font-medium">{form.error}</p>
			{/if}
			{#if form?.formId === 'plans' && form?.success}
				<p role="status" class="text-success text-sm font-medium">{m.plans_saved()}</p>
			{/if}
			<Button type="submit" class="self-start" disabled={savingPlans}>
				{savingPlans ? m.saving() : m.save()}
			</Button>
		</form>
	</section>
{/if}

<section class="bg-card text-card-foreground shadow-card mb-8 rounded-md border p-6">
	<div class="mb-4 flex flex-wrap items-end justify-between gap-4">
		<div>
			<h2 class="text-fancy-title mb-1 text-xl font-semibold">{m.usage_by_month()}</h2>
			<p class="text-muted-foreground text-sm">{m.usage_by_month_desc()}</p>
		</div>
		<form method="GET" class="flex items-end gap-2">
			<div class="space-y-1">
				<label for="month" class="text-sm font-medium">{m.usage_month()}</label>
				<Input id="month" name="month" type="month" value={data.month} class="w-44" />
			</div>
			<Button type="submit" variant="outline">{m.show_month()}</Button>
			<Button
				variant="outline"
				href={`/admin/usage.csv${data.month ? `?month=${data.month}` : ''}`}
				data-sveltekit-reload
			>
				{m.download_csv()}
			</Button>
		</form>
	</div>
	<div class="overflow-x-auto">
		<Table.Root>
			<Table.Header>
				<Table.Row>
					<Table.Head>{m.username()}</Table.Head>
					<Table.Head>{m.admin_plan()}</Table.Head>
					<Table.Head class="text-right">{m.usage_requests()}</Table.Head>
					<Table.Head class="text-right">{m.usage_tokens_in()}</Table.Head>
					<Table.Head class="text-right">{m.usage_tokens_out()}</Table.Head>
					<Table.Head class="text-right">{m.usage_counted()}</Table.Head>
					<Table.Head class="text-right">{m.usage_granted()}</Table.Head>
				</Table.Row>
			</Table.Header>
			<Table.Body>
				{#each data.usageMonth.filter((r: UsageRow) => r.requests > 0 || r.granted > 0) as row (row.user_id)}
					<Table.Row>
						<Table.Cell>{row.username}</Table.Cell>
						<Table.Cell>{planLabel(row.plan)}</Table.Cell>
						<Table.Cell class="text-right">{nf.format(row.requests)}</Table.Cell>
						<Table.Cell class="text-right">{nf.format(row.input_tokens)}</Table.Cell>
						<Table.Cell class="text-right">{nf.format(row.output_tokens)}</Table.Cell>
						<Table.Cell class="text-right">{nf.format(row.cost)}</Table.Cell>
						<Table.Cell class="text-right">{row.granted ? nf.format(row.granted) : '-'}</Table.Cell>
					</Table.Row>
				{:else}
					<Table.Row>
						<Table.Cell colspan={7} class="text-muted-foreground py-4 text-center">-</Table.Cell>
					</Table.Row>
				{/each}
			</Table.Body>
		</Table.Root>
	</div>
</section>

<section class="bg-card text-card-foreground shadow-card mb-8 rounded-md border p-6">
	<h2 class="text-fancy-title mb-2 text-xl font-semibold">{m.toc_reports()}</h2>
	<p class="text-muted-foreground mb-4 text-sm">{m.toc_reports_desc()}</p>
	{#if data.tocReports.length}
		<ul class="flex flex-col gap-3">
			{#each data.tocReports as report (report.id)}
				<li class={['rounded-md border p-3', report.resolved && 'opacity-60']}>
					<div class="flex flex-wrap items-start justify-between gap-2">
						<div class="min-w-0">
							<p class="font-semibold">{report.score_title} — {report.composer}</p>
							<p class="text-muted-foreground text-xs">
								{report.username} · {new Date(report.created_at).toLocaleString()} · score #{report.score_id}
								· <code class="select-all">{report.pdf_path}</code>
							</p>
						</div>
						{#if report.resolved}
							<span class="text-muted-foreground text-xs">{m.toc_report_resolved()}</span>
						{:else}
							<form method="POST" action="?/resolve_toc_report" use:enhance>
								<input type="hidden" name="id" value={report.id} />
								<Button type="submit" variant="outline" size="sm">{m.toc_report_resolve()}</Button>
							</form>
						{/if}
					</div>
					{#if report.comment}
						<p class="mt-2 text-sm whitespace-pre-line">{report.comment}</p>
					{/if}
					<details class="mt-2 text-sm">
						<summary class="text-muted-foreground cursor-pointer text-xs">
							{m.toc_report_sections({ count: report.sections.length })}
						</summary>
						<ol class="mt-1 list-decimal pl-6 text-xs">
							{#each report.sections as sec, i (i)}
								<li>
									p. {sec.page} — {sec.title}
									<span class="text-muted-foreground">({sec.source})</span>
								</li>
							{/each}
						</ol>
					</details>
				</li>
			{/each}
		</ul>
	{:else}
		<p class="text-muted-foreground text-sm">{m.toc_reports_none()}</p>
	{/if}
</section>

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
							<Button variant="outline" size="sm" onclick={() => openEditDialog(row.original)}>
								{m.edit()}
							</Button>
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

<EditPlanDialog bind:open={editDialogOpen} user={selectedUser} />
