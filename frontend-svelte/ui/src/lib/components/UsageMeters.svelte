<script lang="ts">
	import { resolve } from '$app/paths';
	import type { UsageSummary } from '#lib/types.js';
	import { aiUsedPercent, formatBytes, planLabel, storageUsedPercent } from '#lib/usage.js';
	import * as m from '#lib/paraglide/messages.js';

	/** The account's plan with AI and storage meters, and how to get more. */
	let { usage }: { usage: UsageSummary } = $props();

	const aiPercent = $derived(aiUsedPercent(usage));
	const storagePercent = $derived(storageUsedPercent(usage));
</script>

{#snippet meter(id: string, label: string, percent: number, detail: string)}
	<div class="space-y-1.5">
		<div class="flex items-baseline justify-between gap-2 text-sm">
			<span {id} class="font-medium">{label}</span>
			<span class="text-muted-foreground">{detail}</span>
		</div>
		<div
			class="bg-muted h-2 overflow-hidden rounded-full"
			role="meter"
			aria-labelledby={id}
			aria-valuemin={0}
			aria-valuemax={100}
			aria-valuenow={percent}
		>
			<div
				class="h-full rounded-full transition-all {percent >= 90 ? 'bg-destructive' : 'bg-primary'}"
				style="width: {percent}%"
			></div>
		</div>
	</div>
{/snippet}

<div class="space-y-4">
	<p class="text-sm">
		{m.plan_label()}: <span class="font-semibold">{planLabel(usage.plan)}</span>
	</p>
	{@render meter('usage-ai', m.usage_ai(), aiPercent, m.usage_ai_detail({ percent: aiPercent }))}
	{@render meter(
		'usage-storage',
		m.usage_storage(),
		storagePercent,
		m.usage_storage_detail({
			used: formatBytes(usage.storage_used),
			limit: formatBytes(usage.storage_limit)
		})
	)}
	{#if usage.plan !== 'pro'}
		<p class="text-muted-foreground text-sm">
			{m.usage_upgrade()}
			<a href={resolve('/contact')} class="text-primary font-medium hover:underline">
				{m.contact()}
			</a>
		</p>
	{/if}
</div>
