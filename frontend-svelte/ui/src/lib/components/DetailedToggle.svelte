<script lang="ts">
	import * as m from '#lib/paraglide/messages.js';

	/**
	 * "Detailed description" switch for an AI completion. Submits `detailed`
	 * as "true"/"false" (the hidden field is the unchecked value), read with
	 * `formBool` on the server. `form` ties it to a form elsewhere on the page.
	 */
	let {
		checked = false,
		id,
		form = undefined,
		hint = false
	}: { checked?: boolean; id: string; form?: string; hint?: boolean } = $props();
</script>

<div class="flex flex-col gap-1">
	<input type="hidden" name="detailed" value="false" {form} />
	<label for={id} class="inline-flex cursor-pointer items-center gap-2 text-sm font-medium">
		<input
			{id}
			type="checkbox"
			name="detailed"
			value="true"
			{form}
			{checked}
			class="accent-primary size-4"
		/>
		{m.detailed_label()}
	</label>
	{#if hint}
		<p class="text-muted-foreground pl-6 text-xs">{m.detailed_hint()}</p>
	{/if}
</div>
