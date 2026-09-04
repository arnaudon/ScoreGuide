<script lang="ts">
	import type { PageProps } from './$types';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import * as m from '$lib/paraglide/messages.js';

	let { form }: PageProps = $props();
</script>

<div class="flex h-full items-center justify-center pt-10 pb-4">
	<div class="bg-card text-card-foreground shadow-card w-full max-w-md rounded-lg border p-6">
		<div class="mb-4 text-center">
			<img src="/logo.png" alt="ScoreGuide Logo" class="mx-auto mb-2 h-16 w-auto" />
			<h1 class="text-fancy-title text-3xl font-bold">ScoreGuide</h1>
		</div>

		<h2 class="text-fancy-title mb-4 text-center text-xl font-semibold">
			{m.forgot_password()}
		</h2>

		{#if form?.message}
			<p role="status" class="text-success text-sm font-medium">
				{form.message}
			</p>
		{:else}
			<p class="text-muted-foreground mb-4 text-sm">
				{m.forgot_password_description()}
			</p>
			<form method="POST" class="space-y-4" use:enhance>
				<div class="space-y-2">
					<label for="email" class="text-sm leading-none font-medium">{m.email()}</label>
					<Input id="email" name="email" type="email" value={form?.email ?? ''} required />
				</div>

				{#if form?.error}
					<p role="alert" class="text-destructive text-sm font-medium">{form.error}</p>
				{/if}

				<Button type="submit" class="w-full">{m.send_reset_link()}</Button>
			</form>
		{/if}

		<div class="mt-4 text-center text-sm">
			<a href={resolve('/login')} class="text-primary hover:underline">{m.back_to_login()}</a>
		</div>
	</div>
</div>
