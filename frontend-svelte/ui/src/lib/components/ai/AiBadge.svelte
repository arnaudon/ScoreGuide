<script lang="ts">
	import SparklesIcon from '@lucide/svelte/icons/sparkles';
	import * as m from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.js';

	/** Marks a control that spends AI tokens (everything else is free). */
	let { class: className = '' }: { class?: string } = $props();
</script>

<span
	class={cn(
		'bg-primary/10 text-primary inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 align-middle text-[10px] leading-none font-semibold tracking-wide uppercase',
		className
	)}
	title={m.ai_badge_title()}
>
	<SparklesIcon class="size-2.5" aria-hidden="true" />
	{m.ai_badge()}
	<span class="sr-only">({m.ai_badge_title()})</span>
</span>
