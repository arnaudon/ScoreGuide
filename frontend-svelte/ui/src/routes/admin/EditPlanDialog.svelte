<script lang="ts">
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { enhance, type SubmitFunction } from '$app/forms';
	import * as m from '#lib/paraglide/messages.js';
	import type { AdminUser } from '#lib/types.js';

	/** Change a user's plan and their own AI / storage limits (empty: the plan's). */
	let {
		open = $bindable(false),
		user
	}: {
		open: boolean;
		user: AdminUser | null;
	} = $props();

	let error = $state<string | null>(null);

	// Reset the error whenever the dialog is (re)opened for a user.
	$effect(() => {
		if (open) error = null;
	});

	// Only close once the backend accepted the change; otherwise keep the dialog
	// open and show why, so a failed edit isn't silently lost.
	const closeOnSuccess: SubmitFunction = () => {
		error = null;
		return async ({ result, update }) => {
			if (result.type === 'failure') {
				error = (result.data?.error as string | undefined) ?? m.failed_to_save_changes();
				return;
			}
			open = false;
			await update();
		};
	};

	const selectClass =
		'border-input bg-background focus:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus:ring-2 focus:outline-none';
</script>

<Dialog.Root bind:open>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>{m.edit_plan_title({ username: user?.username || '' })}</Dialog.Title>
			<Dialog.Description>{m.edit_plan_desc()}</Dialog.Description>
		</Dialog.Header>
		{#if user}
			<form
				method="POST"
				action="?/set_user_plan"
				use:enhance={closeOnSuccess}
				class="mt-4 space-y-4"
			>
				<input type="hidden" name="user_id" value={user.id} />
				<div class="space-y-2">
					<label for="plan" class="text-sm font-medium">{m.admin_plan()}</label>
					<select id="plan" name="plan" class={selectClass} value={user.plan || 'free'}>
						<option value="free">{m.plan_free()}</option>
						<option value="pro">{m.plan_pro()}</option>
					</select>
				</div>
				<div class="space-y-2">
					<label for="ai_allowance" class="text-sm font-medium">{m.plan_ai_tokens()}</label>
					<Input
						id="ai_allowance"
						name="ai_allowance"
						type="number"
						min="0"
						value={user.ai_allowance ?? ''}
					/>
				</div>
				<div class="space-y-2">
					<label for="storage_limit_mb" class="text-sm font-medium">{m.plan_storage_mb()}</label>
					<Input
						id="storage_limit_mb"
						name="storage_limit_mb"
						type="number"
						min="0"
						value={user.storage_limit_mb ?? ''}
					/>
				</div>
				{#if error}
					<p role="alert" class="text-destructive text-sm font-medium">{error}</p>
				{/if}
				<Dialog.Footer>
					<Button type="submit">{m.save_changes()}</Button>
				</Dialog.Footer>
			</form>
		{/if}
	</Dialog.Content>
</Dialog.Root>
