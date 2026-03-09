<script lang="ts">
	import type { PageProps } from './$types';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';

	let { form }: PageProps = $props();
</script>

<div class="flex h-full items-center justify-center py-20">
	<div class="w-full max-w-sm rounded-lg border bg-card p-8 text-card-foreground shadow-sm">
		<h1 class="mb-6 text-center text-2xl font-bold">Login</h1>

		<form method="POST" class="space-y-4">
			<div class="space-y-2">
				<label for="username" class="text-sm font-medium leading-none">Username</label>
				<Input id="username" name="username" type="text" value={form?.username ?? ''} />
			</div>
			<div class="space-y-2">
				<label for="password" class="text-sm font-medium leading-none">Password</label>
				<Input id="password" name="password" type="password" />
			</div>

			{#if form?.error}
				<p class="text-sm font-medium text-destructive">{form.error}</p>
			{/if}

			<Button type="submit" class="w-full">Log in</Button>
		</form>
	</div>
</div>
