<script lang="ts">
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import * as m from '$lib/paraglide/messages.js';
	import type { Score, Period, Difficulty } from '$lib/types.js';

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

	let title = $state('');
	let composer = $state('');
	let year = $state(1750);
	let period = $state<Period>('Classical');
	let genre = $state('');
	let form = $state('');
	let style = $state('');
	let scoreKey = $state('');
	let instrumentation = $state('');
	let shortDescription = $state('');
	let longDescription = $state('');
	let youtubeUrl = $state('');
	let difficulty = $state<Difficulty>('moderate');
	let notableInterpreters = $state('');
	let saving = $state(false);

	$effect(() => {
		if (score) {
			title = score.title ?? '';
			composer = score.composer ?? '';
			year = score.year ?? 1750;
			period = score.period ?? 'Classical';
			genre = score.genre ?? '';
			form = score.form ?? '';
			style = score.style ?? '';
			scoreKey = score.key ?? '';
			instrumentation = score.instrumentation ?? '';
			shortDescription = score.short_description ?? '';
			longDescription = score.long_description ?? '';
			youtubeUrl = score.youtube_url ?? '';
			difficulty = score.difficulty ?? 'moderate';
			notableInterpreters = score.notable_interpreters ?? '';
		}
	});

	const textareaClass =
		'border-input bg-transparent placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 flex min-h-24 w-full rounded-md border px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50';
	const selectClass =
		'border-input bg-background ring-offset-background focus:ring-ring flex h-9 w-full items-center rounded-md border px-3 py-1 text-sm shadow-xs focus:ring-2 focus:ring-offset-2 focus:outline-none';
</script>

<Sheet.Root bind:open>
	<Sheet.Content class="w-full overflow-y-auto sm:max-w-md">
		<Sheet.Header>
			<Sheet.Title>{m.edit_score()}</Sheet.Title>
			<Sheet.Description>{m.edit_score_desc()}</Sheet.Description>
		</Sheet.Header>
		{#if score}
			<form
				method="POST"
				{action}
				class="mt-6 flex flex-col gap-4"
				use:enhance={() => {
					saving = true;
					return async ({ update, result }) => {
						saving = false;
						if (result.type === 'success') {
							await invalidateAll();
							open = false;
						}
						await update({ reset: false });
					};
				}}
			>
				<input type="hidden" name="id" value={score.id} />

				<div class="space-y-2">
					<label for="edit-title" class="text-sm font-medium">{m.label_title()}</label>
					<Input id="edit-title" name="title" bind:value={title} required />
				</div>
				<div class="space-y-2">
					<label for="edit-composer" class="text-sm font-medium">{m.label_composer()}</label>
					<Input id="edit-composer" name="composer" bind:value={composer} required />
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
						bind:value={year}
					/>
				</div>
				<div class="space-y-2">
					<label for="edit-period" class="text-sm font-medium">{m.label_period()}</label>
					<select id="edit-period" name="period" bind:value={period} class={selectClass}>
						{#each PERIODS as p (p)}
							<option value={p}>{p}</option>
						{/each}
					</select>
				</div>
				<div class="space-y-2">
					<label for="edit-genre" class="text-sm font-medium">{m.label_genre()}</label>
					<Input id="edit-genre" name="genre" bind:value={genre} />
				</div>
				<div class="space-y-2">
					<label for="edit-form" class="text-sm font-medium">{m.label_form()}</label>
					<Input id="edit-form" name="form" bind:value={form} />
				</div>
				<div class="space-y-2">
					<label for="edit-style" class="text-sm font-medium">{m.label_style()}</label>
					<Input id="edit-style" name="style" bind:value={style} />
				</div>
				<div class="space-y-2">
					<label for="edit-key" class="text-sm font-medium">{m.label_key_signature()}</label>
					<Input id="edit-key" name="key" bind:value={scoreKey} />
				</div>
				<div class="space-y-2">
					<label for="edit-instrumentation" class="text-sm font-medium"
						>{m.label_instrumentation()}</label
					>
					<Input id="edit-instrumentation" name="instrumentation" bind:value={instrumentation} />
				</div>
				<div class="space-y-2">
					<label for="edit-difficulty" class="text-sm font-medium">{m.label_difficulty()}</label>
					<select
						id="edit-difficulty"
						name="difficulty"
						bind:value={difficulty}
						class={selectClass}
					>
						{#each DIFFICULTIES as d (d)}
							<option value={d}>{d}</option>
						{/each}
					</select>
				</div>
				<div class="space-y-2">
					<label for="edit-short-description" class="text-sm font-medium"
						>{m.label_short_description()}</label
					>
					<textarea
						id="edit-short-description"
						name="short_description"
						bind:value={shortDescription}
						class={textareaClass}></textarea>
				</div>
				<div class="space-y-2">
					<label for="edit-long-description" class="text-sm font-medium"
						>{m.label_long_description()}</label
					>
					<textarea
						id="edit-long-description"
						name="long_description"
						bind:value={longDescription}
						rows={5}
						class={textareaClass}></textarea>
				</div>
				<div class="space-y-2">
					<label for="edit-notable-interpreters" class="text-sm font-medium"
						>{m.label_notable_interpreters()}</label
					>
					<Input
						id="edit-notable-interpreters"
						name="notable_interpreters"
						bind:value={notableInterpreters}
					/>
				</div>
				<div class="space-y-2">
					<label for="edit-youtube-url" class="text-sm font-medium">{m.label_youtube_url()}</label>
					<Input id="edit-youtube-url" name="youtube_url" bind:value={youtubeUrl} />
				</div>

				<Sheet.Footer class="mt-4">
					<Button type="submit" disabled={saving}>
						{saving ? m.saving() : m.save_changes()}
					</Button>
				</Sheet.Footer>
			</form>
		{/if}
	</Sheet.Content>
</Sheet.Root>
