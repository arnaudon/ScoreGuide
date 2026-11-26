<script lang="ts">
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import ScoreDetails from '#lib/components/ScoreDetails.svelte';
	import type { IMSLPScore, ImslpFile, ImslpResult } from '#lib/types.js';
	import * as m from '#lib/paraglide/messages.js';
	import { httpUrl } from '#lib/url.js';

	/**
	 * Details of an IMSLP work, links to each of its files on IMSLP, and the
	 * form that adds it to the library with the PDF the user downloaded there
	 * (ScoreGuide itself never downloads from IMSLP). Posts to the `add_imslp` action
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
	let dragging = $state(false);

	/** The work's files on IMSLP; null while loading. */
	let imslpFiles = $state<ImslpFile[] | null>(null);
	let showAll = $state(false);
	const SHOWN = 6;
	const visibleFiles = $derived(
		imslpFiles ? (showAll ? imslpFiles : imslpFiles.slice(0, SHOWN)) : []
	);

	// A new work starts with a clean form and loads its file list.
	$effect(() => {
		const id = work?.id;
		const isOpen = open;
		error = null;
		showAll = false;
		imslpFiles = null;
		if (!isOpen || id == null) return;
		const ctrl = new AbortController();
		fetch(`/api/imslp/${id}/files`, { signal: ctrl.signal })
			.then((res) => (res.ok ? res.json() : []))
			.then((list) => {
				imslpFiles = Array.isArray(list) ? list : [];
			})
			.catch(() => {
				if (!ctrl.signal.aborted) imslpFiles = [];
			});
		return () => ctrl.abort();
	});

	function onDrop(event: DragEvent) {
		event.preventDefault();
		dragging = false;
		const file = event.dataTransfer?.files?.[0];
		if (!file) return;
		if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
			error = m.imslp_drop_only_pdf();
			return;
		}
		const picked = new DataTransfer();
		picked.items.add(file);
		files = picked.files;
		error = null;
	}
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
				<div class="flex flex-col gap-2">
					<h4 class="text-sm font-medium">{m.imslp_files_title()}</h4>
					{#if imslpFiles === null}
						<p class="text-muted-foreground text-sm">{m.imslp_files_loading()}</p>
					{:else if imslpFiles.length === 0}
						<p class="text-muted-foreground text-sm">
							{m.imslp_files_none()}
							{#if httpUrl(work.permlink)}
								<br />
								<a
									href={httpUrl(work.permlink)}
									target="_blank"
									rel="external noopener noreferrer"
									class="text-primary break-all hover:underline">{work.permlink}</a
								>
							{/if}
						</p>
					{:else}
						<p class="text-muted-foreground text-xs">{m.imslp_files_hint()}</p>
						<ul
							class="divide-border border-border max-h-56 divide-y overflow-y-auto rounded-md border"
						>
							{#each visibleFiles as file, i (i)}
								<li class="flex items-center justify-between gap-3 px-3 py-2 text-sm">
									<div class="min-w-0">
										<p class="truncate font-medium" title={file.file}>
											{file.description || file.file}
										</p>
										{#if file.copyright}
											<p class="text-muted-foreground truncate text-xs">{file.copyright}</p>
										{/if}
									</div>
									{#if httpUrl(file.url)}
										<a
											href={httpUrl(file.url)}
											target="_blank"
											rel="external noopener noreferrer"
											class="text-primary shrink-0 hover:underline">{m.imslp_files_open()}</a
										>
									{/if}
								</li>
							{/each}
						</ul>
						{#if !showAll && imslpFiles.length > SHOWN}
							<button
								type="button"
								class="text-primary self-start text-sm hover:underline"
								onclick={() => (showAll = true)}
								>{m.imslp_files_more({ count: imslpFiles.length })}</button
							>
						{/if}
					{/if}
				</div>
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
							>{m.imslp_drop_title()}</label
						>
						<p class="text-muted-foreground text-xs">{m.imslp_drop_hint()}</p>
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
								ondragover={(event) => {
									event.preventDefault();
									dragging = true;
								}}
								ondragleave={() => (dragging = false)}
								ondrop={onDrop}
								class="border-input hover:bg-accent hover:text-accent-foreground flex min-h-20 w-full cursor-pointer items-center justify-center rounded-md border border-dashed bg-transparent px-3 py-3 text-sm shadow-xs transition-colors {dragging
									? 'border-primary bg-accent'
									: ''}"
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
