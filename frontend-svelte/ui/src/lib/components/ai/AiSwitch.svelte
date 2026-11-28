<script lang="ts">
	import SparklesIcon from '@lucide/svelte/icons/sparkles';
	import * as m from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.js';

	/** On / off switch for an AI feature (off: its free, AI-less counterpart). */
	let {
		checked,
		disabled = false,
		onChange,
		label = m.ai_switch()
	}: {
		checked: boolean;
		disabled?: boolean;
		onChange: (value: boolean) => void;
		label?: string;
	} = $props();
</script>

<button
	type="button"
	role="switch"
	aria-checked={checked}
	{disabled}
	title={m.ai_badge_title()}
	class="focus-visible:ring-ring inline-flex items-center gap-2 rounded-full text-xs font-medium focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
	onclick={() => onChange(!checked)}
>
	<SparklesIcon
		class={cn('size-3.5', checked ? 'text-primary' : 'text-muted-foreground')}
		aria-hidden="true"
	/>
	<span class={checked ? 'text-foreground' : 'text-muted-foreground'}>{label}</span>
	<span
		class={cn(
			'relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors',
			checked ? 'bg-primary' : 'bg-input'
		)}
		aria-hidden="true"
	>
		<span
			class={cn(
				'bg-background size-3 rounded-full shadow transition-transform',
				checked ? 'translate-x-3.5' : 'translate-x-0.5'
			)}
		></span>
	</span>
</button>
