<script lang="ts">
	import type { PageProps } from './$types';
	import { resolve } from '$app/paths';
	import * as m from '#lib/paraglide/messages.js';

	let { data }: PageProps = $props();
</script>

<div class="flex h-full items-center justify-center pt-10 pb-4">
	<div class="bg-card text-card-foreground shadow-card w-full max-w-md rounded-lg border p-6">
		<div class="mb-4 text-center">
			<img src="/logo.png" alt="ScoreGuide Logo" class="mx-auto mb-2 h-16 w-auto" />
			<h1 class="text-fancy-title text-3xl font-bold">ScoreGuide</h1>
		</div>
		<h2 class="text-fancy-title mb-4 text-center text-xl font-semibold">{m.verify_title()}</h2>
		{#if data.verified}
			<p role="status" class="text-success text-sm font-medium">{m.verify_success()}</p>
		{:else}
			<p role="alert" class="text-destructive text-sm font-medium">{m.verify_failed()}</p>
		{/if}
		<div class="mt-4 text-center text-sm">
			<a
				href={data.loggedIn ? resolve('home') : resolve('login')}
				class="text-primary hover:underline"
				>{data.loggedIn ? m.verify_continue() : m.back_to_login()}</a
			>
		</div>
	</div>
</div>
