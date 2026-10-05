<script lang="ts">
	import type { PageProps } from './$types';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import * as m from '$lib/paraglide/messages.js';

	let { data, form }: PageProps = $props();
</script>

<div class="flex h-full items-center justify-center pt-10 pb-4">
	<div class="bg-card text-card-foreground shadow-card w-full max-w-md rounded-lg border p-6">
		<div class="mb-4 text-center">
			<img src="/logo.png" alt="ScoreGuide Logo" class="mx-auto mb-2 h-16 w-auto" />
			<h1 class="text-fancy-title text-3xl font-bold">ScoreGuide</h1>
		</div>

		<h2 class="text-fancy-title mb-4 text-center text-xl font-semibold">
			{m.reset_password()}
		</h2>

		{#if form?.success}
			<p role="status" class="text-success text-sm font-medium">
				{form.message}
			</p>
			<div class="mt-4 text-center text-sm">
				<a href={resolve('/login')} class="text-primary hover:underline">{m.back_to_login()}</a>
			</div>
		{:else if !data.token}
			<p role="alert" class="text-destructive text-sm font-medium">{m.invalid_reset_link()}</p>
			<div class="mt-4 text-center text-sm">
				<a href={resolve('/forgot-password')} class="text-primary hover:underline"
					>{m.request_new_reset_link()}</a
				>
			</div>
		{:else}
			<form method="POST" class="space-y-4" use:enhance>
				<input type="hidden" name="token" value={form?.token ?? data.token} />
				<div class="space-y-2">
					<label for="new_password" class="text-sm leading-none font-medium"
						>{m.new_password()}</label
					>
					<Input id="new_password" name="new_password" type="password" required />
				</div>
				<div class="space-y-2">
					<label for="confirm_password" class="text-sm leading-none font-medium"
						>{m.confirm_password()}</label
					>
					<Input id="confirm_password" name="confirm_password" type="password" required />
				</div>

				{#if form?.error}
					<p role="alert" class="text-destructive text-sm font-medium">{form.error}</p>
				{/if}

				<Button type="submit" class="w-full">{m.reset_password()}</Button>
			</form>
		{/if}
	</div>
</div>
