<script lang="ts">
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import ScoreDetails from '#lib/components/ScoreDetails.svelte';
	import type { IMSLPScore, ImslpResult } from '#lib/types.js';
	import * as m from '#lib/paraglide/messages.js';

	/**
	 * Details of an IMSLP work and the form that adds it to the library with
	 * the PDF the user downloaded from IMSLP. Posts to the `add_imslp` action
	 * of the score list page (`action`), from wherever it is shown.
	 */
	let {
		work = $bindable(),
		open = $bindable(false),
		action = '?/add_imslp',
		onAdded
	}: {
		work: IMSLPScore | ImslpResult | null;
		open?: boolean;
		action?: string;
		onAdded?: (scoreId: number | null) => void;
	} = $props();

	let uploading = $state(false);
	let error = $state<string | null>(null);
	let files = $state<FileList | undefined>();

	// A new work starts with a clean form.
	$effect(() => {
		void work;
		error = null;
	});
</script>

<Dialog.Root bind:open>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title class="text-fancy-title text-2xl"
				>{work?.title || m.imslp_score_details()}</Dialog.Title
			>
			<Dialog.Description>{work?.composer || m.imslp_score_details_desc()}</Dialog.Description>
		</Dialog.Header>
		{#if work}
			<ScoreDetails score={work} />

			<div class="border-border flex flex-col gap-4 border-t pt-4">
				<h3 class="text-foreground font-semibold">{m.add_this_score()}</h3>
				<p class="text-muted-foreground text-sm">
					{m.download_pdf_imslp()}<br />
					<a
						href={work.permlink}
						target="_blank"
						rel="external noopener noreferrer"
						class="text-primary break-all hover:underline">{work.permlink}</a
					>
				</p>
				<p class="text-muted-foreground text-sm">
					{m.upload_pdf_below()}
				</p>
				<form
					method="POST"
					{action}
					enctype="multipart/form-data"
					use:enhance={() => {
						uploading = true;
						error = null;
						return async ({ update, result }) => {
							uploading = false;
							// Keep the dialog, chosen work and PDF on failure so the user can retry.
							if (result.type === 'failure') {
								error = (result.data?.error as string) || m.err_add_score();
								return;
							}
							const scoreId = result.type === 'success' ? result.data?.scoreId : null;
							work = null;
							open = false;
							files = undefined;
							// Another page's action must not land in this page's `form` prop.
							if (action.startsWith('?')) await update();
							else await invalidateAll();
							onAdded?.(typeof scoreId === 'number' ? scoreId : null);
						};
					}}
					class="flex flex-col gap-4"
				>
					<input type="hidden" name="imslp_id" value={work.id} />
					<div class="space-y-2">
						<label for="imslp_file_sheet" class="text-sm leading-none font-medium"
							>{m.pdf_file()}</label
						>
						<div class="relative">
							<Input
								id="imslp_file_sheet"
								name="file"
								type="file"
								accept="application/pdf"
								required
								class="sr-only"
								bind:files
							/>
							<label
								for="imslp_file_sheet"
								class="border-input hover:bg-accent hover:text-accent-foreground flex h-9 w-full cursor-pointer items-center rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs transition-colors"
							>
								<span class="text-muted-foreground truncate">
									{files && files.length > 0 ? files[0].name : m.choose_file()}
								</span>
							</label>
						</div>
					</div>
					<Button type="submit" disabled={uploading} class="w-full">
						{uploading ? m.adding() : m.add_score()}
					</Button>
					{#if error}
						<p role="alert" class="text-destructive text-sm font-medium">{error}</p>
					{/if}
				</form>
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>
