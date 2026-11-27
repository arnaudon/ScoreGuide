<script lang="ts">
	import type { PageProps } from './$types';
	import { onMount } from 'svelte';
	import { page as appPage } from '$app/state';
	import { goto, invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import ListIcon from '@lucide/svelte/icons/list';
	import PanelLeftClose from '@lucide/svelte/icons/panel-left-close';
	import InfoIcon from '@lucide/svelte/icons/info';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import Maximize from '@lucide/svelte/icons/maximize';
	import ScoreDetailsDialog from '#lib/components/ScoreDetailsDialog.svelte';
	import EditScoreDialog from '#lib/components/EditScoreDialog.svelte';
	import ScoreContents from '#lib/components/ScoreContents.svelte';
	import ScoreViewer from '#lib/components/ScoreViewer.svelte';
	import ReaderTabs from '#lib/components/ReaderTabs.svelte';
	import AnnotationLayer, { type Tool } from '#lib/components/AnnotationLayer.svelte';
	import AnnotationTools, { COLORS } from '#lib/components/AnnotationTools.svelte';
	import { annotationsApi, localAnnotationsApi } from '#lib/annotations.js';
	import { AnnotationStore } from '#lib/viewer/annotations.svelte.js';
	import * as m from '#lib/paraglide/messages.js';

	let { data, form }: PageProps = $props();

	const pill =
		'text-foreground hover:bg-accent hover:text-accent-foreground focus-visible:ring-ring inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none';
	let sheetOpen = $state(false);
	// Larger screens: a foldable side panel next to the score. It starts
	// open only when there is something to navigate (2+ sections) and the
	// reader hasn't folded it before (remembered per browser); toggling it
	// on this page overrides that. Small screens (and full screen): the
	// viewer's own contents drawer.
	let tocPanelPref = $state(true);
	let tocPanelToggled: boolean | null = $state(null);
	let tocPanelOpen = $derived(tocPanelToggled ?? (tocPanelPref && data.toc.sections.length > 1));
	let currentPage = $state(0);
	const TOC_PANEL_KEY = 'reader.tocPanelOpen';

	onMount(() => {
		try {
			tocPanelPref = localStorage.getItem(TOC_PANEL_KEY) !== 'false';
		} catch {
			// Storage unavailable (private mode…): keep the default.
		}
	});

	function setTocPanel(open: boolean) {
		tocPanelToggled = open;
		try {
			localStorage.setItem(TOC_PANEL_KEY, String(open));
		} catch {
			// Not persisted; still toggled for this visit.
		}
	}

	function toggleContents() {
		if (window.matchMedia('(min-width: 768px)').matches) {
			setTocPanel(!tocPanelOpen);
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
	// The read-only demo account keeps them in this browser instead.
	let notes = $derived(
		data.score?.id
			? new AnnotationStore(
					appPage.data.isDemo ? localAnnotationsApi(data.score.id) : annotationsApi(data.score.id)
				)
			: null
	);
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

	// Same-origin proxy: the httpOnly access_token cookie rides along and
	// /api/pdf authenticates server-side, so the token never appears in a URL.
	let filename = $derived(data.score?.pdf_path || '');
	let pdfUrl = $derived(filename ? `/api/pdf/${encodeURIComponent(filename)}` : '');
</script>

<!-- Sized to the viewport (minus the layout's padding) so the viewer always
     fits on screen and a long contents list scrolls inside its own panel
     instead of stretching the page. -->
<div
	class="flex h-[calc(100dvh-5rem)] min-h-[28rem] w-full flex-col gap-4 p-1 sm:p-2 lg:h-[calc(100dvh-8rem)]"
>
	<ReaderTabs
		currentId={Number(appPage.params.id)}
		current={data.score?.id
			? { id: data.score.id, title: data.score.title ?? '', composer: data.score.composer ?? '' }
			: null}
	/>
	{#if data.score}
		<header class="flex items-center justify-between gap-3">
			<div class="min-w-0">
				<h1 class="text-fancy-title text-foreground truncate text-xl font-bold sm:text-2xl">
					{data.score.title}
				</h1>
				<p class="text-muted-foreground truncate text-sm">{data.score.composer}</p>
			</div>
			<!-- One compact pill: icons everywhere, labels from sm up. -->
			<div
				role="toolbar"
				aria-label={data.score.title}
				class="bg-card shadow-card flex shrink-0 items-center gap-0.5 rounded-full border p-1"
			>
				<button
					type="button"
					class={[pill, tocPanelOpen && 'bg-accent text-accent-foreground']}
					onclick={toggleContents}
					aria-expanded={tocPanelOpen}
					aria-label={m.toc_contents()}
					title={m.toc_contents()}
				>
					<ListIcon class="size-4" />
					<span class="hidden sm:inline">{m.toc_contents()}</span>
					{#if data.toc.sections.length}
						<span
							class="bg-muted text-muted-foreground rounded-full px-1.5 text-xs leading-5 tabular-nums"
							>{data.toc.sections.length}</span
						>
					{/if}
				</button>
				<button
					type="button"
					class={pill}
					onclick={() => (sheetOpen = true)}
					aria-label={m.view_details()}
					title={m.view_details()}
				>
					<InfoIcon class="size-4" />
					<span class="hidden sm:inline">{m.view_details()}</span>
				</button>
				{#if !appPage.data.isDemo}
					<button
						type="button"
						class={pill}
						onclick={() => (editOpen = true)}
						aria-label={m.edit_score()}
						title={m.edit_score()}
					>
						<PencilIcon class="size-4" />
						<span class="hidden lg:inline">{m.edit_score()}</span>
					</button>
				{/if}
				<span class="bg-border mx-0.5 h-5 w-px"></span>
				<button
					type="button"
					class="bg-primary text-primary-foreground hover:bg-primary/90 focus-visible:ring-ring inline-flex size-9 items-center justify-center rounded-full transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:opacity-50"
					onclick={() => viewer?.toggleFullscreen()}
					disabled={!pdfUrl}
					aria-label={m.viewer_fullscreen()}
					title={m.viewer_fullscreen()}
				>
					<Maximize class="size-4" />
				</button>
			</div>
		</header>

		<div class="flex min-h-0 flex-1 gap-3">
			{#if tocPanelOpen}
				<aside
					aria-label={m.toc_contents()}
					class="bg-card shadow-card hidden w-64 shrink-0 flex-col gap-2 overflow-y-auto rounded-md border p-3 md:flex lg:w-72"
				>
					<div class="flex items-center justify-between gap-2">
						<h2 class="text-sm font-semibold">{m.toc_contents()}</h2>
						<button
							type="button"
							class="text-muted-foreground hover:bg-accent hover:text-accent-foreground inline-flex size-8 items-center justify-center rounded-md"
							onclick={() => setTocPanel(false)}
							aria-label={m.toc_fold()}
							title={m.toc_fold()}
						>
							<PanelLeftClose class="size-4" />
						</button>
					</div>
					<!-- Tabs switch scores in place: a fresh panel per score, so a
					     report sent for one doesn't show as sent for the next. -->
					{#key data.score.id}
						<ScoreContents
							toc={data.toc}
							error={!!form?.tocError}
							canNavigate={!!pdfUrl}
							{currentPage}
							onSelect={goToPage}
						/>
					{/key}
				</aside>
			{/if}
			<div class="bg-card shadow-card relative min-h-0 flex-1 overflow-hidden rounded-md border">
				{#if pdfUrl}
					<!-- A fresh viewer per score (tabs switch scores in place), so the
					     page it restores and saves never leaks from one to the next. -->
					{#key data.score.id}
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
								{#if notes}
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
										{notes.error === 'load'
											? m.annotations_load_error()
											: m.annotations_save_error()}
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
					{/key}
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

<ScoreDetailsDialog
	score={data.score}
	bind:open={sheetOpen}
	user={data.user}
	showOpen={false}
	onEdit={() => (editOpen = true)}
	onDeleted={() => goto(resolve('/db-viewer'))}
/>

<EditScoreDialog bind:open={editOpen} score={data.score} />
