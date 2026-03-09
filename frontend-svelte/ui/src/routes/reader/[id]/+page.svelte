<script lang="ts">
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// Fallback to title or ID if filename isn't directly on the score model
	const filename = data.score?.filename || data.score?.title || data.score?.id;
	
	// PDF.js viewer is hosted at /pdfjs/web/viewer.html on the backend
	// We pass the actual PDF endpoint (/pdf/{filename}) with the token as the ?file= parameter
	const pdfUrl = `${data.backendUrl}/pdf/${filename}?token=${data.token}`;
	const viewerUrl = `${data.backendUrl}/pdfjs/web/viewer.html?file=${encodeURIComponent(pdfUrl)}`;
</script>

<div class="h-full w-full p-4">
	{#if data.score}
		<div class="mb-4 flex items-center justify-between">
			<h1 class="text-2xl font-bold text-foreground">{data.score.title}</h1>
			<p class="text-muted-foreground">{data.score.composer}</p>
		</div>
		
		<div class="rounded-md border bg-card shadow-sm h-[calc(100vh-8rem)]">
			<iframe 
				src={viewerUrl} 
				class="w-full h-full border-0 rounded-md" 
				title="PDF Viewer"
			></iframe>
		</div>
	{:else}
		<div class="p-8 text-center text-muted-foreground">
			<h2 class="text-xl font-bold">Score not found.</h2>
			<p>We could not find the details for this score.</p>
		</div>
	{/if}
</div>
