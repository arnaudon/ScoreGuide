<script lang="ts">
	import { page } from '$app/state';
	import { locales, localizeHref } from '$lib/paraglide/runtime';
	import '../app.css';

	const { children } = $props();
</script>

<div class="flex h-screen bg-gray-50">
	<!-- Sidebar -->
	<aside class="w-64 bg-white border-r shadow-sm flex flex-col">
		<div class="p-4 border-b">
			<h2 class="text-xl font-bold text-gray-800">App Menu</h2>
		</div>
		<nav class="p-4 flex flex-col gap-2 flex-1">
			<a href="/" class="p-2 hover:bg-gray-100 rounded text-gray-700">Home</a>
			<a href="/login" class="p-2 hover:bg-gray-100 rounded text-gray-700">Login</a>
			<a href="/db-viewer" class="p-2 hover:bg-gray-100 rounded text-gray-700">Database Viewer</a>
		</nav>
	</aside>

	<!-- Main Content -->
	<main class="flex-1 overflow-y-auto">
		{@render children()}
	</main>
</div>

<div style="display:none">
	{#each locales as locale}
		<a href={localizeHref(page.url.pathname, { locale })}>{locale}</a>
	{/each}
</div>
