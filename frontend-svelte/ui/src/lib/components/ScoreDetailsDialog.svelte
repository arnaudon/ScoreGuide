<script lang="ts">
	import { enhance } from '$app/forms';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { invalidateAll } from '$app/navigation';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import ScoreDetails from '#lib/components/ScoreDetails.svelte';
	import TrashIcon from '@lucide/svelte/icons/trash-2';
	import SparklesIcon from '@lucide/svelte/icons/sparkles';
	import PencilIcon from '@lucide/svelte/icons/pencil';
	import BookOpenIcon from '@lucide/svelte/icons/book-open';
	import { aiLeftLabel } from '#lib/usage.js';
	import type { Score, User } from '#lib/types.js';
	import * as m from '#lib/paraglide/messages.js';

	/**
	 * The library score card: details plus delete / rerun the AI / edit / open.
	 * Shared by the library, the reader and the home page so they all show the
	 * same thing. The actions live on the library route (/db-viewer).
	 */
	let {
		score,
		open = $bindable(false),
		user = undefined,
		showOpen = true,
		onEdit,
		onDeleted
	}: {
		score: Score | null | undefined;
		open?: boolean;
		user?: Pick<User, 'usage'> | null;
		/** Show the "open the score" button (not needed inside the reader). */
		showOpen?: boolean;
		onEdit: () => void;
		onDeleted?: () => void;
	} = $props();

	let recompleting = $state(false);
	let recompleteError = $state<string | null>(null);
	let deleteError = $state<string | null>(null);
	let aiLeft = $derived(aiLeftLabel(user));

	$effect(() => {
		void score?.id;
		recompleteError = null;
		deleteError = null;
	});
</script>

<Dialog.Root bind:open>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title class="text-fancy-title text-2xl"
				>{score?.title || m.score_details()}</Dialog.Title
			>
			<Dialog.Description>{score?.composer || m.score_details_desc()}</Dialog.Description>
		</Dialog.Header>
		{#if score}
			<ScoreDetails {score} />

			<!-- The forms are empty: their buttons sit in the action row below
			     and point at them with the form attribute. -->
			<form
				id="recomplete-form"
				method="POST"
				action="/db-viewer?/recomplete"
				hidden
				use:enhance={() => {
					recompleting = true;
					recompleteError = null;
					return async ({ result }) => {
						recompleting = false;
						if (result.type === 'success') {
							await invalidateAll();
						} else if (result.type === 'failure') {
							recompleteError = (result.data?.error as string) || m.failed_to_complete_score();
						} else if (result.type === 'error') {
							recompleteError = m.failed_to_complete_score();
						}
					};
				}}
			>
				<input type="hidden" name="id" value={score.id} />
			</form>
			<form
				id="delete-form"
				method="POST"
				action="/db-viewer?/delete"
				hidden
				use:enhance={() => {
					deleteError = null;
					return async ({ result }) => {
						// Shown inside the dialog: a page banner would be hidden behind it.
						if (result.type === 'success') {
							open = false;
							onDeleted?.();
							await invalidateAll();
						} else if (result.type === 'failure') {
							deleteError = (result.data?.error as string) || m.err_delete_score();
						} else if (result.type === 'error') {
							deleteError = m.err_delete_score();
						}
					};
				}}
			>
				<input type="hidden" name="id" value={score.id} />
			</form>

			<div class="border-border flex flex-col gap-2 border-t pt-4">
				{#if recompleteError}
					<p role="alert" class="text-destructive text-sm font-medium">{recompleteError}</p>
				{/if}
				{#if deleteError}
					<p role="alert" class="text-destructive text-sm font-medium">{deleteError}</p>
				{/if}
				<div class="flex flex-wrap items-center gap-2">
					{#if !page.data.isDemo}
						<Button
							type="submit"
							form="delete-form"
							variant="ghost"
							size="icon"
							class="text-destructive hover:bg-destructive/10 hover:text-destructive"
							aria-label={m.delete_score()}
							title={m.delete_score()}
						>
							<TrashIcon />
						</Button>
					{/if}
					<span class="flex-1"></span>
					{#if !page.data.isDemo}
						<Button
							type="submit"
							form="recomplete-form"
							variant="outline"
							disabled={recompleting}
							title={aiLeft}
						>
							<SparklesIcon />{recompleting ? m.running_agent() : m.rerun_complete_agent()}
						</Button>
						<Button
							variant="outline"
							onclick={() => {
								open = false;
								onEdit();
							}}
						>
							<PencilIcon />{m.edit_score()}
						</Button>
					{/if}
					{#if showOpen}
						<Button href={resolve('/reader/[id]', { id: String(score.id) })}>
							<BookOpenIcon />{m.view_pdf()}
						</Button>
					{/if}
				</div>
				{#if !page.data.isDemo && aiLeft}
					<p class="text-muted-foreground text-end text-xs">{aiLeft}</p>
				{/if}
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>
