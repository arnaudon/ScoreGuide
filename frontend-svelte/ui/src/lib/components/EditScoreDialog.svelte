<script lang="ts">
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import * as m from '#lib/paraglide/messages.js';
	import type { Score, Period, Difficulty } from '#lib/types.js';
	import { FORMS, GENRES, formLabel, genreLabel } from '#lib/metadata.js';

	const CURRENT_YEAR = new Date().getFullYear();

	let {
		open = $bindable(false),
		score,
		action = '?/update_score'
	}: {
		open: boolean;
		score: Score | null | undefined;
		action?: string;
	} = $props();

	const PERIODS: Period[] = [
		'Medieval',
		'Renaissance',
		'Baroque',
		'Classical',
		'Romantic',
		'Modernist',
		'Postmodernist'
	];
	const DIFFICULTIES: Difficulty[] = ['easy', 'moderate', 'intermediate', 'advanced', 'expert'];

	function fieldsFromScore(s: Score | null | undefined) {
		return {
			title: s?.title ?? '',
			composer: s?.composer ?? '',
			year: s?.year ?? 1750,
			period: (s?.period ?? 'Classical') as Period,
			genre: s?.genre ?? '',
			form: s?.form ?? '',
			style: s?.style ?? '',
			scoreKey: s?.key ?? '',
			instrumentation: s?.instrumentation ?? '',
			shortDescription: s?.short_description ?? '',
			longDescription: s?.long_description ?? '',
			youtubeUrl: s?.youtube_url ?? '',
			difficulty: (s?.difficulty ?? 'moderate') as Difficulty,
			notableInterpreters: s?.notable_interpreters ?? ''
		};
	}

	// Single object instead of 14 separate $state vars, so adding a field to
	// the form only means touching fieldsFromScore() — not two places that
	// are easy to forget to keep in sync. Seeded with defaults (not `score`
	// itself) so this stays a plain initial value rather than a reactive
	// read — the $effect below is what actually syncs it to `score`.
	let fields = $state(fieldsFromScore(undefined));
	let saving = $state(false);
	let saveError = $state<string | null>(null);

	$effect(() => {
		if (score) {
			fields = fieldsFromScore(score);
		}
	});

	$effect(() => {
		if (open) saveError = null;
	});

	const textareaClass =
		'border-input bg-transparent placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 flex min-h-24 w-full rounded-md border px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50';
	/** The list, plus a stored value from before the fixed vocabulary. */
	const withCurrent = (list: string[], current: string) =>
		current && !list.includes(current) ? [current, ...list] : list;

	const selectClass =
		'border-input bg-background ring-offset-background focus:ring-ring flex h-9 w-full items-center rounded-md border px-3 py-1 text-sm shadow-xs focus:ring-2 focus:ring-offset-2 focus:outline-none';
</script>

<Dialog.Root bind:open>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>{m.edit_score()}</Dialog.Title>
			<Dialog.Description>{m.edit_score_desc()}</Dialog.Description>
		</Dialog.Header>
		{#if score}
			<form
				method="POST"
				{action}
				class="mt-6 flex flex-col gap-4"
				use:enhance={() => {
					saving = true;
					saveError = null;
					return async ({ update, result }) => {
						saving = false;
						if (result.type === 'success') {
							await invalidateAll();
							open = false;
						} else if (result.type === 'failure') {
							saveError = (result.data?.error as string) || m.failed_to_save_changes();
						}
						await update({ reset: false });
					};
				}}
			>
				<input type="hidden" name="id" value={score.id} />

				<div class="space-y-2">
					<label for="edit-title" class="text-sm font-medium">{m.label_title()}</label>
					<Input id="edit-title" name="title" bind:value={fields.title} required />
				</div>
				<div class="space-y-2">
					<label for="edit-composer" class="text-sm font-medium">{m.label_composer()}</label>
					<Input id="edit-composer" name="composer" bind:value={fields.composer} required />
				</div>
				<div class="space-y-2">
					<label for="edit-year" class="text-sm font-medium">{m.label_year()}</label>
					<Input
						id="edit-year"
						name="year"
						type="number"
						step="1"
						min={-999}
						max={CURRENT_YEAR + 1}
						bind:value={fields.year}
					/>
				</div>
				<div class="space-y-2">
					<label for="edit-period" class="text-sm font-medium">{m.label_period()}</label>
					<select id="edit-period" name="period" bind:value={fields.period} class={selectClass}>
						{#each PERIODS as p (p)}
							<option value={p}>{p}</option>
						{/each}
					</select>
				</div>
				<div class="space-y-2">
					<label for="edit-genre" class="text-sm font-medium">{m.label_genre()}</label>
					<select id="edit-genre" name="genre" bind:value={fields.genre} class={selectClass}>
						<option value="">{m.option_none()}</option>
						{#each withCurrent(GENRES, fields.genre) as g (g)}
							<option value={g}>{genreLabel(g)}</option>
						{/each}
					</select>
				</div>
				<div class="space-y-2">
					<label for="edit-form" class="text-sm font-medium">{m.label_form()}</label>
					<select id="edit-form" name="form" bind:value={fields.form} class={selectClass}>
						<option value="">{m.option_none()}</option>
						{#each withCurrent(FORMS, fields.form) as f (f)}
							<option value={f}>{formLabel(f)}</option>
						{/each}
					</select>
				</div>
				<div class="space-y-2">
					<label for="edit-style" class="text-sm font-medium">{m.label_style()}</label>
					<Input id="edit-style" name="style" bind:value={fields.style} />
				</div>
				<div class="space-y-2">
					<label for="edit-key" class="text-sm font-medium">{m.label_key_signature()}</label>
					<Input id="edit-key" name="key" bind:value={fields.scoreKey} />
				</div>
				<div class="space-y-2">
					<label for="edit-instrumentation" class="text-sm font-medium">
						{m.label_instrumentation()}
					</label>
					<Input
						id="edit-instrumentation"
						name="instrumentation"
						bind:value={fields.instrumentation}
					/>
				</div>
				<div class="space-y-2">
					<label for="edit-difficulty" class="text-sm font-medium">{m.label_difficulty()}</label>
					<select
						id="edit-difficulty"
						name="difficulty"
						bind:value={fields.difficulty}
						class={selectClass}
					>
						{#each DIFFICULTIES as d (d)}
							<option value={d}>{d}</option>
						{/each}
					</select>
				</div>
				<div class="space-y-2">
					<label for="edit-short-description" class="text-sm font-medium">
						{m.label_short_description()}
					</label>
					<textarea
						id="edit-short-description"
						name="short_description"
						bind:value={fields.shortDescription}
						class={textareaClass}></textarea>
				</div>
				<div class="space-y-2">
					<label for="edit-long-description" class="text-sm font-medium">
						{m.label_long_description()}
					</label>
					<textarea
						id="edit-long-description"
						name="long_description"
						bind:value={fields.longDescription}
						rows={5}
						class={textareaClass}></textarea>
				</div>
				<div class="space-y-2">
					<label for="edit-notable-interpreters" class="text-sm font-medium">
						{m.label_notable_interpreters()}
					</label>
					<Input
						id="edit-notable-interpreters"
						name="notable_interpreters"
						bind:value={fields.notableInterpreters}
					/>
				</div>
				<div class="space-y-2">
					<label for="edit-youtube-url" class="text-sm font-medium">{m.label_youtube_url()}</label>
					<Input id="edit-youtube-url" name="youtube_url" bind:value={fields.youtubeUrl} />
				</div>

				{#if saveError}
					<p role="alert" class="text-destructive text-sm font-medium">{saveError}</p>
				{/if}

				<Dialog.Footer class="mt-4">
					<Button type="submit" disabled={saving}>
						{saving ? m.saving() : m.save_changes()}
					</Button>
				</Dialog.Footer>
			</form>
		{/if}
	</Dialog.Content>
</Dialog.Root>
