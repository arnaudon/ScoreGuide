<script lang="ts">
	import type { PageProps } from './$types';
	import { onMount } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import EditScoreDialog from '$lib/components/EditScoreDialog.svelte';
	import ScoreContents from '$lib/components/ScoreContents.svelte';
	import { isLocalizedField, localizedField } from '$lib/i18n/score.js';
	import * as m from '$lib/paraglide/messages.js';

	let { data, form }: PageProps = $props();
	let sheetOpen = $state(false);
	// Small screens: contents in a sheet. Larger screens: a side panel next
	// to the score, open by default and collapsible (remembered per browser).
	let tocSheetOpen = $state(false);
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
			tocSheetOpen = true;
		}
	}
	let editOpen = $state(false);
	let iframeEl: HTMLIFrameElement | undefined = $state();
	// Tracks which viewer URL has actually fired `onload`, rather than a
	// plain boolean, so navigating to a different score's PDF while this
	// component stays mounted correctly goes back to "loading" instead of
	// keeping the previous document's loaded state.
	let loadedUrl = $state('');

	function enterPresentationMode() {
		const button = iframeEl?.contentWindow?.document?.getElementById('presentationMode');
		if (button) {
			button.click();
		} else {
			console.error('Presentation mode control not found in the PDF viewer.');
		}
	}

	type PdfViewerApp = {
		page: number;
		initializedPromise?: Promise<void>;
		eventBus?: { on: (name: string, cb: (e: { pageNumber: number }) => void) => void };
	};
	type PdfViewerWindow = Window & { PDFViewerApplication?: PdfViewerApp };

	function viewerApp(): PdfViewerApp | undefined {
		return (iframeEl?.contentWindow as PdfViewerWindow | null)?.PDFViewerApplication;
	}

	function goToPage(page: number) {
		const viewer = viewerApp();
		if (viewer) {
			viewer.page = page;
			currentPage = page;
			tocSheetOpen = false;
		} else {
			console.error('PDF viewer not ready for navigation.');
		}
	}

	// Follow the page shown in the viewer so the contents can highlight the
	// section being read.
	function onViewerLoad() {
		loadedUrl = viewerUrl;
		const viewer = viewerApp();
		viewer?.initializedPromise?.then(() => {
			viewer.eventBus?.on('pagechanging', (e) => (currentPage = e.pageNumber));
		});
	}

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

	// Use the saved pdf_path from the database.
	let filename = $derived(data.score?.pdf_path || '');

	// PDF.js viewer is hosted at /pdfjs/web/viewer.html. It fetches the
	// `file` URL from the same origin, so the httpOnly access_token cookie
	// rides along and the /api/pdf proxy authenticates server-side. The
	// token never appears in any URL the browser sees.
	let pdfUrl = $derived(filename ? `/api/pdf/${encodeURIComponent(filename)}` : '');
	let viewerUrl = $derived(
		pdfUrl ? `/pdfjs/web/viewer.html?file=${encodeURIComponent(pdfUrl)}` : ''
	);
	let pdfLoaded = $derived(viewerUrl !== '' && loadedUrl === viewerUrl);
</script>

<div class="flex h-full min-h-0 w-full flex-col gap-4 p-4">
	{#if data.score}
		<div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
			<div>
				<h1 class="text-fancy-title text-foreground text-2xl font-bold">{data.score.title}</h1>
				<p class="text-muted-foreground">{data.score.composer}</p>
			</div>
			<div class="flex flex-wrap gap-2">
				<Button variant="outline" onclick={enterPresentationMode} disabled={!pdfLoaded}>
					{m.presentation_mode()}
				</Button>
				<Button variant="outline" onclick={toggleContents} aria-expanded={tocPanelOpen}>
					{m.toc_contents()}{data.toc.sections.length ? ` (${data.toc.sections.length})` : ''}
				</Button>
				<Button variant="outline" onclick={() => (sheetOpen = true)}>{m.view_details()}</Button>
				<Button variant="outline" onclick={() => (editOpen = true)}>{m.edit_score()}</Button>
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
						canNavigate={pdfLoaded}
						{currentPage}
						onSelect={goToPage}
					/>
				</aside>
			{/if}
			<div class="bg-card shadow-card relative min-h-0 flex-1 rounded-md border">
				{#if viewerUrl}
					{#if !pdfLoaded}
						<Skeleton class="absolute inset-0 rounded-md" />
					{/if}
					<iframe
						bind:this={iframeEl}
						src={viewerUrl}
						onload={onViewerLoad}
						class="h-full w-full rounded-md border-0"
						title="PDF Viewer"
						allowfullscreen
					></iframe>
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

<Sheet.Root bind:open={tocSheetOpen}>
	<Sheet.Content side="left" class="w-full overflow-y-auto sm:max-w-md">
		<Sheet.Header>
			<Sheet.Title>{m.toc_contents()}</Sheet.Title>
			<Sheet.Description>{m.toc_desc()}</Sheet.Description>
		</Sheet.Header>
		<div class="mt-4 px-4 pb-6">
			<ScoreContents
				toc={data.toc}
				error={!!form?.tocError}
				canNavigate={pdfLoaded}
				{currentPage}
				onSelect={goToPage}
			/>
		</div>
	</Sheet.Content>
</Sheet.Root>

<EditScoreDialog bind:open={editOpen} score={data.score} />
