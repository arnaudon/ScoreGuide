<script lang="ts">
	import type { PageProps } from './$types';
	import { onMount } from 'svelte';
	import { page as appPage } from '$app/state';
	import { invalidateAll } from '$app/navigation';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Sheet from '#lib/components/ui/sheet/index.js';
	import EditScoreDialog from '#lib/components/EditScoreDialog.svelte';
	import ScoreContents from '#lib/components/ScoreContents.svelte';
	import ScoreViewer from '#lib/components/ScoreViewer.svelte';
	import AnnotationLayer, { type Tool } from '#lib/components/AnnotationLayer.svelte';
	import AnnotationTools, { COLORS } from '#lib/components/AnnotationTools.svelte';
	import { annotationsApi } from '#lib/annotations.js';
	import { AnnotationStore } from '#lib/viewer/annotations.svelte.js';
	import { isLocalizedField, localizedField } from '#lib/i18n/score.js';
	import * as m from '#lib/paraglide/messages.js';

	let { data, form }: PageProps = $props();
	let sheetOpen = $state(false);
	// Larger screens: a side panel next to the score, open by default and
	// collapsible (remembered per browser). Small screens (and full screen):
	// the viewer's own contents drawer.
	let tocPanelOpen = $state(true);
	let currentPage = $state(0);
	const TOC_PANEL_KEY = 'reader.tocPanelOpen';

	onMount(() => {
		try {
			tocPanelOpen = localStorage.getItem(TOC_PANEL_KEY) !== 'false';
		} catch {
			// Storage unavailable (private mode…): keep the default.
		}
	});

	function toggleContents() {
		if (window.matchMedia('(min-width: 768px)').matches) {
			tocPanelOpen = !tocPanelOpen;
			try {
				localStorage.setItem(TOC_PANEL_KEY, String(tocPanelOpen));
			} catch {
				// Not persisted; still toggled for this visit.
			}
		} else {
			viewer?.openContents();
		}
	}
	let editOpen = $state(false);
	let viewer: ScoreViewer | undefined = $state();

	function goToPage(page: number) {
		viewer?.goTo(page);
	}

	// The user's pencil marks and notes for this score, saved as they go.
	let tool: Tool = $state(null);
	let penColor = $state(COLORS[0].value);
	let notes = $derived(data.score?.id ? new AnnotationStore(annotationsApi(data.score.id)) : null);
	$effect(() => {
		void notes?.load();
	});

	// While the table of contents is being generated in the background,
	// refresh the page data every few seconds until it's done.
	$effect(() => {
		if (data.toc.status !== 'running') return;
		const timer = setInterval(() => invalidateAll(), 4000);
		return () => clearInterval(timer);
	});

	function translateKey(key: string) {
		const map: Record<string, string> = {
			title: m.label_title(),
			composer: m.label_composer(),
			year: m.label_year(),
			period: m.label_period(),
			instrumentation: m.label_instrumentation(),
			short_description: m.label_short_description(),
			key: m.label_key_signature(),
			genre: m.label_genre(),
			form: m.label_form(),
			style: m.label_style(),
			long_description: m.label_long_description(),
			difficulty: m.label_difficulty(),
			notable_interpreters: m.label_notable_interpreters(),
			notable_interpeters: m.label_notable_interpreters(),
			youtube_url: m.label_youtube_url(),
			permlink: m.label_permlink()
		};
		return map[key] || key.replace(/_/g, ' ');
	}

	// Same-origin proxy: the httpOnly access_token cookie rides along and
	// /api/pdf authenticates server-side, so the token never appears in a URL.
	let filename = $derived(data.score?.pdf_path || '');
	let pdfUrl = $derived(filename ? `/api/pdf/${encodeURIComponent(filename)}` : '');
</script>

<div class="flex h-full min-h-0 w-full flex-col gap-4 p-4">
	{#if data.score}
		<div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
			<div>
				<h1 class="text-fancy-title text-foreground text-2xl font-bold">{data.score.title}</h1>
				<p class="text-muted-foreground">{data.score.composer}</p>
			</div>
			<div class="flex flex-wrap gap-2">
				<Button variant="outline" onclick={() => viewer?.toggleFullscreen()} disabled={!pdfUrl}>
					{m.viewer_fullscreen()}
				</Button>
				<Button variant="outline" onclick={toggleContents} aria-expanded={tocPanelOpen}>
					{m.toc_contents()}{data.toc.sections.length ? ` (${data.toc.sections.length})` : ''}
				</Button>
				<Button variant="outline" onclick={() => (sheetOpen = true)}>{m.view_details()}</Button>
				{#if !appPage.data.isDemo}
					<Button variant="outline" onclick={() => (editOpen = true)}>{m.edit_score()}</Button>
				{/if}
			</div>
		</div>

		<div class="flex min-h-0 flex-1 gap-3">
			{#if tocPanelOpen}
				<aside
					aria-label={m.toc_contents()}
					class="bg-card shadow-card hidden w-64 shrink-0 overflow-y-auto rounded-md border p-3 md:block lg:w-72"
				>
					<ScoreContents
						toc={data.toc}
						error={!!form?.tocError}
						canNavigate={!!pdfUrl}
						{currentPage}
						onSelect={goToPage}
					/>
				</aside>
			{/if}
			<div class="bg-card shadow-card relative min-h-0 flex-1 overflow-hidden rounded-md border">
				{#if pdfUrl}
					<ScoreViewer
						bind:this={viewer}
						bind:page={currentPage}
						url={pdfUrl}
						storageKey={`reader.page.${data.score.id}`}
						label={data.score.title ?? 'PDF'}
						interactive={tool === null}
					>
						{#snippet overlay({ page, width, height })}
							{#if notes}
								<AnnotationLayer
									{width}
									{height}
									items={notes.forPage(page)}
									{tool}
									color={penColor}
									onCreate={(d) => notes.create(page, d)}
									onUpdate={(id, d) => notes.update(id, d)}
									onDelete={(id) => notes.remove(id)}
								/>
							{/if}
						{/snippet}
						{#snippet tools()}
							<!-- The demo account is read-only: no annotate button. -->
							{#if notes && !appPage.data.isDemo}
								<AnnotationTools
									bind:tool
									bind:color={penColor}
									canUndo={notes.canUndo}
									onUndo={() => notes.undo()}
								/>
							{/if}
						{/snippet}
						{#snippet banner()}
							{#if notes?.error}
								<div
									role="alert"
									class="bg-destructive text-destructive-foreground flex items-center gap-3 rounded-md px-3 py-2 text-sm shadow-lg"
								>
									{notes.error === 'load' ? m.annotations_load_error() : m.annotations_save_error()}
									<button type="button" class="underline" onclick={() => notes?.dismissError()}
										>{m.dismiss()}</button
									>
								</div>
							{/if}
						{/snippet}
						{#snippet contents(goTo)}
							<ScoreContents
								toc={data.toc}
								error={!!form?.tocError}
								canNavigate
								{currentPage}
								onSelect={goTo}
							/>
						{/snippet}
					</ScoreViewer>
				{:else}
					<div class="text-muted-foreground flex h-full items-center justify-center">
						{m.no_pdf_available()}
					</div>
				{/if}
			</div>
		</div>
	{:else}
		<div class="text-muted-foreground p-8 text-center">
			<h2 class="text-xl font-bold">{m.score_not_found()}</h2>
			<p>{m.score_not_found_desc()}</p>
		</div>
	{/if}
</div>

<Sheet.Root bind:open={sheetOpen}>
	<Sheet.Content class="w-full overflow-y-auto sm:max-w-md">
		<Sheet.Header>
			<Sheet.Title>{m.score_details()}</Sheet.Title>
			<Sheet.Description>{m.score_details_desc()}</Sheet.Description>
		</Sheet.Header>
		{#if data.score}
			<div class="mt-6 flex flex-col gap-3">
				{#each Object.entries(data.score)
					.filter(([k]) => !['id', 'user_id', 'pdf_path', 'number_of_plays', 'source', 'imslp_id', 'short_description_fr', 'long_description_fr'].includes(k))
					.sort(([a], [b]) => {
						const order = ['title', 'composer', 'year', 'period', 'instrumentation', 'short_description', 'key', 'genre', 'form', 'style', 'long_description', 'difficulty', 'notable_interpreters', 'notable_interpeters', 'youtube_url'];
						const idxA = order.indexOf(a);
						const idxB = order.indexOf(b);
						if (idxA !== -1 && idxB !== -1) return idxA - idxB;
						if (idxA !== -1) return -1;
						if (idxB !== -1) return 1;
						return a.localeCompare(b);
					}) as [key, value] (key)}
					<div class="border-border grid grid-cols-3 gap-2 border-b pb-2 last:border-0">
						<span class="text-foreground text-sm font-semibold capitalize">
							{translateKey(key)}
						</span>
						<span class="text-muted-foreground col-span-2 text-sm break-words">
							{#if key === 'youtube_url' && value}
								<a
									href={value as string}
									target="_blank"
									rel="external noopener noreferrer"
									class="text-primary hover:underline"
								>
									{m.watch_on_youtube()}
								</a>
							{:else if isLocalizedField(key) && data.score}
								{localizedField(data.score, key) || value || '-'}
							{:else}
								{value !== null && value !== '' ? value : '-'}
							{/if}
						</span>
					</div>
				{/each}
			</div>
		{/if}
	</Sheet.Content>
</Sheet.Root>

<EditScoreDialog bind:open={editOpen} score={data.score} />
