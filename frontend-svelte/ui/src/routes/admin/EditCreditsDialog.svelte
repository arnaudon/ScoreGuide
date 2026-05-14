<script lang="ts">
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { enhance } from '$app/forms';
	import * as m from '$lib/paraglide/messages.js';
	import type { AdminUser } from '$lib/types.js';

	let {
		open = $bindable(false),
		user
	}: {
		open: boolean;
		user: AdminUser | null;
	} = $props();

	let max_credits = $state(0);

	$effect(() => {
		if (user) {
			max_credits = user.max_credits ?? 20;
		}
	});

	function closeOnSubmit() {
		return async ({ update }: { update: () => Promise<void> }) => {
			open = false;
			await update();
		};
	}
</script>

<Sheet.Root bind:open>
	<Sheet.Content>
		<Sheet.Header>
			<Sheet.Title>{m.edit_max_credits({ username: user?.username || '' })}</Sheet.Title>
			<Sheet.Description>
				{m.edit_max_credits_desc()}
			</Sheet.Description>
		</Sheet.Header>
		{#if user}
			<div class="mt-4 space-y-6">
				<form method="POST" action="?/set_credits" use:enhance={closeOnSubmit} class="space-y-4">
					<input type="hidden" name="user_id" value={user.id} />
					<div class="space-y-2">
						<label for="max_credits" class="text-sm font-medium">{m.max_credits()}</label>
						<Input id="max_credits" name="max_credits" type="number" bind:value={max_credits} />
					</div>
					<Sheet.Footer>
						<Button type="submit">{m.save_changes()}</Button>
					</Sheet.Footer>
				</form>

				<form method="POST" action="?/refill_credits" use:enhance={closeOnSubmit}>
					<input type="hidden" name="user_id" value={user.id} />
					<Button
						variant="outline"
						type="submit"
						class="w-full"
						disabled={user.credits === user.max_credits}
					>
						{m.refill_credits()}
					</Button>
				</form>
			</div>
		{/if}
	</Sheet.Content>
</Sheet.Root>
