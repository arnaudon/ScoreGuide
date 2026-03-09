<script lang="ts">
	import { page } from '$app/state';
	import { locales, localizeHref } from '$lib/paraglide/runtime';
	import '../app.css';
	import AppSidebar from '$lib/components/Sidebar.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';

	const { children } = $props();
</script>

<Sidebar.Provider>
	<!-- Sidebar -->
	<AppSidebar />

	<!-- Main Content -->
	<main class="flex-1 overflow-y-auto w-full bg-gray-50">
		{@render children()}
	</main>
</Sidebar.Provider>

<div style="display:none">
	{#each locales as locale}
		<a href={localizeHref(page.url.pathname, { locale })}>{locale}</a>
	{/each}
</div>
