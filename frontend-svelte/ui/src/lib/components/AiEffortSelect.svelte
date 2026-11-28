<script lang="ts">
	import { untrack } from 'svelte';
	import * as m from '#lib/paraglide/messages.js';
	import { EFFORTS, type Effort, canAfford, defaultEffort, effortPercent } from '#lib/usage.js';
	import type { User } from '#lib/types.js';

	/**
	 * How much the AI may do (and spend) to fill in a score, with what one run
	 * typically takes of the account's tokens. Submits `effort`
	 * (`none` = no AI, only when `allowNone`). `form` ties it to a form elsewhere.
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

	function cost(effort: Effort): string {
		if (!canAfford(user, effort)) return m.effort_too_costly();
		const percent = effortPercent(user, effort);
		if (percent === undefined) return '';
		return m.effort_cost({ percent: percent < 1 ? '<1' : String(Math.round(percent)) });
	}
</script>

<div class="flex flex-col gap-1">
	<div class="flex flex-wrap items-center gap-2">
		<label for={id} class="text-sm font-medium">{m.effort_label()}</label>
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
				<option value={effort} disabled={!canAfford(user, effort)}>
					{LABELS[effort]()}{note ? ` · ${note}` : ''}
				</option>
			{/each}
		</select>
	</div>
	<p class="text-muted-foreground text-xs">
		{#if fallback === null && allowNone}{m.effort_none_left()}{:else}{DESCRIPTIONS[
				value ?? 'none'
			]()}{/if}
	</p>
</div>
