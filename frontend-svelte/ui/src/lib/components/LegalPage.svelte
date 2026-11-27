<script lang="ts">
	import type { Snippet } from 'svelte';

	/** Shared layout of the long-form public pages (privacy, terms, legal, contact). */
	let {
		title,
		updated = '',
		children
	}: { title: string; updated?: string; children: Snippet } = $props();
</script>

<svelte:head>
	<title>{title} · ScoreGuide</title>
</svelte:head>

<article class="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
	<header class="border-border mb-8 border-b pb-6">
		<h1 class="text-fancy-title text-4xl font-semibold sm:text-5xl">{title}</h1>
		{#if updated}
			<p class="text-muted-foreground mt-2 text-sm">{updated}</p>
		{/if}
	</header>
	<div class="prose max-w-none prose-h2:mt-10 prose-h2:text-2xl prose-li:my-1">
		{@render children()}
	</div>
</article>
