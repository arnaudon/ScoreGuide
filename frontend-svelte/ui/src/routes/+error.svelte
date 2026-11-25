<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import * as m from '#lib/paraglide/messages.js';

	// Messages from the server can be English or internal: show our own text.
	let message = $derived(
		page.status === 404
			? m.error_not_found()
			: page.status === 503
				? m.err_service_unavailable()
				: m.err_something_went_wrong()
	);
	let home = $derived(page.data.loggedIn ? resolve('home') : resolve('/'));
</script>

<svelte:head>
	<title>{page.status} · ScoreGuide</title>
</svelte:head>

<div class="flex h-full items-center justify-center pt-10 pb-4">
	<div
		class="bg-card text-card-foreground shadow-card w-full max-w-md rounded-lg border p-6 text-center"
	>
		<img src="/logo.png" alt="ScoreGuide Logo" class="mx-auto mb-2 h-16 w-auto" />
		<h1 class="text-fancy-title mb-2 text-3xl font-bold">{page.status}</h1>
		<p role="alert" class="text-muted-foreground mb-4">{message}</p>
		<a href={home} class="text-primary hover:underline">{m.error_back_home()}</a>
	</div>
</div>
