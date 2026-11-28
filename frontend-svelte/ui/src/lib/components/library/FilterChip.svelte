<script lang="ts">
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down';
	import * as Popover from '#lib/components/ui/popover/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import type { Tally } from '#lib/library.js';
	import * as m from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.js';

	/** A filter button opening a list of values with their counts (several can be ticked). */
	let {
		label,
		options,
		selected,
		onChange,
		valueLabel = (v: string) => v,
		class: className = ''
	} = $props<{
		label: string;
		options: Tally[];
		selected: string[];
		onChange: (values: string[]) => void;
		valueLabel?: (value: string) => string;
		class?: string;
	}>();

	function toggle(value: string, on: boolean) {
		onChange(on ? [...selected, value] : selected.filter((v: string) => v !== value));
	}
</script>

<Popover.Root>
	<Popover.Trigger
		class={cn(
			'hover:bg-accent focus-visible:ring-ring inline-flex h-8 items-center gap-1 rounded-full border px-3 text-sm transition-colors focus-visible:ring-2 focus-visible:outline-none',
			selected.length ? 'border-primary bg-primary/10 text-primary' : 'text-foreground',
			className
		)}
	>
		{label}
		{#if selected.length}
			<span class="bg-primary text-primary-foreground rounded-full px-1.5 text-xs tabular-nums">
				{selected.length}
			</span>
		{/if}
		<ChevronDownIcon class="size-3.5 opacity-60" aria-hidden="true" />
	</Popover.Trigger>
	<Popover.Content class="max-h-80 overflow-y-auto p-1">
		{#if options.length === 0}
			<p class="text-muted-foreground p-2 text-sm">{m.filter_none()}</p>
		{/if}
		<ul>
			{#each options as option (option.name)}
				{@const checked = selected.includes(option.name)}
				<li>
					<label
						class="hover:bg-accent flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm"
					>
						<Checkbox {checked} onCheckedChange={(on) => toggle(option.name, on === true)} />
						<span class="min-w-0 flex-1 truncate">{valueLabel(option.name)}</span>
						<span class="text-muted-foreground text-xs tabular-nums">{option.count}</span>
					</label>
				</li>
			{/each}
		</ul>
	</Popover.Content>
</Popover.Root>
