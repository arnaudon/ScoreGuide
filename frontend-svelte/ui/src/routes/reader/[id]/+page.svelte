<script lang="ts">
	import type { PageProps } from './$types';
	import { Button } from '$lib/components/ui/button/index.js';
	import Maximize from 'lucide-svelte/icons/maximize';
	import Minimize from 'lucide-svelte/icons/minimize';

	let { data }: PageProps = $props();

	// Use the saved pdf_path from the database
	let filename = $derived(data.score?.pdf_path || '');
	
	// PDF.js viewer is hosted at /pdfjs/web/viewer.html on the backend
	// We pass the absolute URL to ensure PDF.js correctly parses the query parameters instead of URL-encoding them into the filename
	let pdfUrl = $derived(filename ? `${data.backendUrl}/pdf/${encodeURIComponent(filename)}?token=${data.token}` : '');
	let viewerUrl = $derived(pdfUrl ? `${data.backendUrl}/pdfjs/web/viewer.html?file=${encodeURIComponent(pdfUrl)}` : '');

	let iframeEl: HTMLIFrameElement | undefined = $state();
	let isFullscreen = $state(false);

	$effect(() => {
		const handleFullscreenChange = () => {
			isFullscreen = !!document.fullscreenElement;
		};
		document.addEventListener('fullscreenchange', handleFullscreenChange);
		return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
	});

	function toggleFullscreen() {
		if (!document.fullscreenElement) {
			try {
				// Try to enter PDF.js presentation mode (hides toolbar, fits page to screen)
				// Note: this will only work if the iframe and host are same-origin.
				const pdfApp = (iframeEl?.contentWindow as any)?.PDFViewerApplication;
				if (pdfApp && typeof pdfApp.requestPresentationMode === 'function') {
					pdfApp.requestPresentationMode();
					return;
				}
			} catch (e) {
				// Ignore CORS errors and fall back to standard iframe fullscreen
				console.warn('Cross-origin frame: falling back to standard fullscreen');
			}

			iframeEl?.requestFullscreen().catch((err) => {
				console.error(`Error attempting to enable fullscreen: ${err.message}`);
			});
		} else {
			document.exitFullscreen();
		}
	}
</script>

<div class="h-full w-full p-4">
	{#if data.score}
		<div class="mb-4 flex items-center justify-between">
			<div>
				<h1 class="text-2xl font-bold text-foreground">{data.score.title}</h1>
				<p class="text-muted-foreground">{data.score.composer}</p>
			</div>
			<Button variant="outline" onclick={toggleFullscreen}>
				{#if isFullscreen}
					<Minimize class="mr-2 h-4 w-4" />
					Exit Fullscreen
				{:else}
					<Maximize class="mr-2 h-4 w-4" />
					Fullscreen
				{/if}
			</Button>
		</div>
		
		<div class="rounded-md border bg-card shadow-sm h-[calc(100vh-8rem)]">
			{#if viewerUrl}
				<iframe 
					bind:this={iframeEl}
					src={viewerUrl} 
					class="w-full h-full border-0 rounded-md bg-white dark:bg-zinc-900" 
					title="PDF Viewer"
					allowfullscreen
				></iframe>
			{:else}
				<div class="flex h-full items-center justify-center text-muted-foreground">
					No PDF available for this score.
				</div>
			{/if}
		</div>
	{:else}
		<div class="p-8 text-center text-muted-foreground">
			<h2 class="text-xl font-bold">Score not found.</h2>
			<p>We could not find the details for this score.</p>
		</div>
	{/if}
</div>
