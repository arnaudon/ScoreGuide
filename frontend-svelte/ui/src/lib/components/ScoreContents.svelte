<script lang="ts">
	import { enhance } from '$app/forms';
	import { page } from '$app/state';
	import { Button } from '#lib/components/ui/button/index.js';
	import type { ScoreSection, SectionsResponse } from '#lib/types.js';
	import * as m from '#lib/paraglide/messages.js';

	let {
		toc,
		error = false,
		canNavigate,
		currentPage = 0,
		onSelect
	}: {
		toc: SectionsResponse;
		/** The last Rebuild request failed. */
		error?: boolean;
		/** The PDF viewer is ready to jump to a page. */
		canNavigate: boolean;
		/** Page currently shown in the viewer (0 = unknown). */
		currentPage?: number;
		onSelect: (page: number) => void;
	} = $props();

	let rebuilding = $state(false);

	const confidenceLabel = {
		high: m.toc_confidence_high,
		medium: m.toc_confidence_medium,
		low: m.toc_confidence_low
	};
	const confidenceDot = { high: 'bg-emerald-500', medium: 'bg-amber-500', low: 'bg-red-500' };
	// Built by an older detector: offer the improved one.
	let outdated = $derived(
		toc.status === 'ready' && toc.version !== null && toc.version < toc.latest_version
	);
	// "This table of contents is wrong": a short note sent to the admins,
	// with a snapshot of the sections, to improve the detector.
	let reportOpen = $state(false);
	let reporting = $state(false);
	let reported = $state(false);
	let reportFailed = $state(false);
	// Rendered twice on the reader page (side panel and viewer drawer).
	const uid = $props.id();

	// Pieces with their movements (level 1 entries follow their piece).
	let groups = $derived.by(() => {
		const out: { section: ScoreSection; movements: ScoreSection[] }[] = [];
		for (const section of toc.sections) {
			const last = out.at(-1);
			if (section.level > 0 && last) last.movements.push(section);
			else out.push({ section, movements: [] });
		}
		return out;
	});

	// The section being read: the last one starting at or before the page.
	let activeId = $derived.by(() => {
		let active: number | null = null;
		for (const section of toc.sections) {
			if (currentPage && section.page <= currentPage) active = section.id;
		}
		return active;
	});
</script>

<div class="flex flex-col gap-3">
	{#if toc.status === 'running'}
		<p role="status" class="text-muted-foreground text-sm">{m.toc_running()}</p>
	{:else if toc.status === 'error' || error}
		<p role="alert" class="text-destructive text-sm font-medium">{m.toc_error()}</p>
	{/if}

	{#snippet entry(section: ScoreSection, movement: boolean)}
		<button
			type="button"
			onclick={() => onSelect(section.page)}
			disabled={!canNavigate}
			aria-current={section.id === activeId ? 'true' : undefined}
			class={[
				'hover:bg-accent focus-visible:ring-ring aria-[current]:border-primary aria-[current]:bg-accent flex w-full flex-col gap-1 rounded-md border text-left transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:opacity-60',
				movement ? 'p-1.5' : 'p-2'
			]}
		>
			<span class="flex items-baseline justify-between gap-2">
				<span
					class={['text-foreground', movement ? 'text-xs font-medium' : 'text-sm font-semibold']}
				>
					{section.title}
				</span>
				<span class="text-muted-foreground shrink-0 text-xs">
					{m.toc_page({ page: section.page })}
				</span>
			</span>
			{#if section.incipit_path}
				<img
					src={`/api/incipit/${section.score_id}/${section.id}`}
					alt={m.toc_incipit_alt({ title: section.title })}
					loading="lazy"
					class="w-full rounded-sm bg-white dark:brightness-90"
				/>
			{/if}
		</button>
	{/snippet}

	{#if toc.sections.length}
		<ol class="flex flex-col gap-2">
			{#each groups as group (group.section.id)}
				<li>
					{@render entry(group.section, false)}
					{#if group.movements.length}
						<ol
							class="border-border mt-1 ml-3 flex flex-col gap-1 border-l pl-2"
							aria-label={m.toc_movements({ title: group.section.title })}
						>
							{#each group.movements as section (section.id)}
								<li>{@render entry(section, true)}</li>
							{/each}
						</ol>
					{/if}
				</li>
			{/each}
		</ol>
	{:else if toc.status !== 'running'}
		<p class="text-muted-foreground text-sm">{m.toc_empty()}</p>
	{/if}

	{#if toc.status === 'ready' && toc.confidence}
		<div class="flex flex-col gap-1">
			<p class="text-muted-foreground flex items-center gap-2 text-xs">
				<span
					class={['size-2 shrink-0 rounded-full', confidenceDot[toc.confidence]]}
					aria-hidden="true"
				></span>
				{m.toc_confidence({ level: confidenceLabel[toc.confidence]() })}
			</p>
			{#if toc.confidence === 'low'}
				<p class="text-muted-foreground text-xs">{m.toc_confidence_low_hint()}</p>
			{/if}
		</div>
	{/if}

	{#if outdated && !page.data.isDemo}
		<p
			role="status"
			class="border-primary/40 bg-primary/5 text-foreground rounded-md border p-2 text-sm"
		>
			{m.toc_outdated()}
		</p>
	{/if}

	{#if toc.status !== 'running' && !page.data.isDemo}
		<form
			method="POST"
			action="?/generate_toc"
			use:enhance={() => {
				rebuilding = true;
				return async ({ update }) => {
					rebuilding = false;
					await update({ reset: false });
				};
			}}
		>
			<Button
				type="submit"
				variant={outdated ? 'default' : 'outline'}
				size="sm"
				class="w-full"
				disabled={rebuilding}
			>
				{m.toc_rebuild()}
			</Button>
		</form>
	{/if}

	{#if toc.status !== 'running' && !page.data.isDemo}
		{#if reported}
			<p role="status" class="text-muted-foreground text-sm">{m.toc_report_thanks()}</p>
		{:else if !reportOpen}
			<button
				type="button"
				class="text-muted-foreground hover:text-foreground self-start text-xs underline-offset-2 hover:underline"
				onclick={() => (reportOpen = true)}
			>
				{m.toc_report()}
			</button>
		{:else}
			<form
				method="POST"
				action="?/report_toc"
				class="flex flex-col gap-2"
				use:enhance={() => {
					reporting = true;
					reportFailed = false;
					return async ({ result }) => {
						reporting = false;
						if (result.type === 'success') reported = true;
						else reportFailed = true;
					};
				}}
			>
				<label for="{uid}-toc-report-comment" class="text-sm font-medium">{m.toc_report()}</label>
				<textarea
					id="{uid}-toc-report-comment"
					name="comment"
					maxlength="1000"
					rows="3"
					placeholder={m.toc_report_placeholder()}
					class="border-input bg-background focus-visible:ring-ring rounded-md border p-2 text-sm focus-visible:ring-2 focus-visible:outline-none"
				></textarea>
				{#if reportFailed}
					<p role="alert" class="text-destructive text-sm">{m.toc_report_error()}</p>
				{/if}
				<div class="flex gap-2">
					<Button type="submit" size="sm" disabled={reporting}>{m.toc_report_send()}</Button>
					<Button type="button" variant="ghost" size="sm" onclick={() => (reportOpen = false)}>
						{m.toc_report_cancel()}
					</Button>
				</div>
			</form>
		{/if}
	{/if}
</div>
