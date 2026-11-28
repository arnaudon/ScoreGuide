<script lang="ts">
	import { untrack } from 'svelte';
	import * as m from '#lib/paraglide/messages.js';
	import {
		EFFORTS,
		type Effort,
		canAfford,
		defaultEffort,
		effortAllowed,
		effortMultiple,
		effortPercent
	} from '#lib/usage.js';
	import type { Score, User } from '#lib/types.js';
	import * as Dialog from '#lib/components/ui/dialog/index.js';
	import ScoreDetails from '#lib/components/ScoreDetails.svelte';
	import AiBadge from '#lib/components/ai/AiBadge.svelte';
	import NoAiTokens from '#lib/components/ai/NoAiTokens.svelte';

	/**
	 * How much the AI may do (and spend) to fill in a score, with what one run
	 * typically takes of the account's tokens. Submits `effort`
	 * (`none` = no AI, only when `allowNone`). `form` ties it to a form elsewhere.
	 * Efforts the plan doesn't include (detailed on the free plan) are shown but
	 * disabled, with "See an example" opening a demo description.
	 */
	let {
		user,
		id,
		form = undefined,
		allowNone = false,
		value = $bindable<Effort | 'none'>()
	}: {
		user: Pick<User, 'usage' | 'role' | 'detailed_descriptions'> | null | undefined;
		id: string;
		form?: string;
		allowNone?: boolean;
		value?: Effort | 'none';
	} = $props();

	const LABELS: Record<Effort | 'none', () => string> = {
		none: m.effort_none,
		quick: m.effort_quick,
		standard: m.effort_standard,
		detailed: m.effort_detailed
	};
	const DESCRIPTIONS: Record<Effort | 'none', () => string> = {
		none: m.effort_none_desc,
		quick: m.effort_quick_desc,
		standard: m.effort_standard_desc,
		detailed: m.effort_detailed_desc
	};

	const fallback = $derived(defaultEffort(user));
	// The first choice only: later token changes don't override the user's pick.
	if (value === undefined) value = untrack(() => fallback ?? (allowNone ? 'none' : 'quick'));

	const usable = (effort: Effort) => effortAllowed(user, effort) && canAfford(user, effort);
	const locked = $derived(EFFORTS.filter((effort) => !effortAllowed(user, effort)));

	function cost(effort: Effort): string {
		if (!effortAllowed(user, effort)) return m.effort_pro_only();
		if (!canAfford(user, effort)) return m.effort_too_costly();
		const notes: string[] = [];
		const times = effortMultiple(user, effort);
		if (times !== undefined) notes.push(m.effort_times({ times: String(times) }));
		const percent = effortPercent(user, effort);
		if (percent !== undefined)
			notes.push(m.effort_cost({ percent: percent < 1 ? '<1' : String(Math.round(percent)) }));
		return notes.join(' · ');
	}

	let exampleOpen = $state(false);
	let example = $state<Score | null | undefined>(undefined);
	async function showExample() {
		exampleOpen = true;
		if (example) return;
		try {
			const res = await fetch('/api/demo-example');
			example = res.ok ? ((await res.json()) as Score) : null;
		} catch {
			example = null;
		}
	}
</script>

<div class="flex flex-col gap-1">
	<div class="flex flex-wrap items-center gap-2">
		<label for={id} class="inline-flex items-center gap-1.5 text-sm font-medium">
			{m.effort_label()}
			<AiBadge />
		</label>
		<select
			{id}
			name="effort"
			{form}
			bind:value
			class="border-input bg-background focus-visible:ring-ring h-8 rounded-md border px-2 text-sm focus-visible:ring-2 focus-visible:outline-none"
		>
			{#if allowNone}
				<option value="none">{LABELS.none()}</option>
			{/if}
			{#each EFFORTS as effort (effort)}
				{@const note = cost(effort)}
				<option value={effort} disabled={!usable(effort)}>
					{LABELS[effort]()}{note ? ` · ${note}` : ''}
				</option>
			{/each}
		</select>
	</div>
	{#if fallback === null}
		<NoAiTokens />
	{:else}
		<p class="text-muted-foreground text-xs">{DESCRIPTIONS[value ?? 'none']()}</p>
	{/if}
	{#if locked.length}
		<p class="text-muted-foreground text-xs">
			{LABELS[locked[0]]()}: {m.effort_pro_only()} ·
			<button
				type="button"
				class="text-primary underline-offset-2 hover:underline"
				onclick={showExample}
			>
				{m.effort_example()}
			</button>
		</p>
	{/if}
</div>

<Dialog.Root bind:open={exampleOpen}>
	<Dialog.Content class="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
		<Dialog.Header>
			<Dialog.Title>{m.effort_example_title()}</Dialog.Title>
			<Dialog.Description>{m.effort_example_intro()}</Dialog.Description>
		</Dialog.Header>
		{#if example}
			<ScoreDetails score={example} />
		{:else if example === null}
			<p class="text-muted-foreground text-sm">{m.effort_example_missing()}</p>
		{:else}
			<p class="text-muted-foreground text-sm">…</p>
		{/if}
	</Dialog.Content>
</Dialog.Root>
