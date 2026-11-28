<script lang="ts">
	import StarIcon from '@lucide/svelte/icons/star';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as m from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.js';

	/** Star toggle: the parent changes `favorite` at once and reverts on failure. */
	let {
		favorite,
		onToggle,
		class: className = ''
	}: { favorite: boolean; onToggle: (value: boolean) => void; class?: string } = $props();
	const label = $derived(favorite ? m.favorite_remove() : m.favorite_add());
</script>

<Button
	variant="ghost"
	size="icon"
	class={cn('size-8', className)}
	aria-label={label}
	aria-pressed={favorite}
	title={label}
	onclick={(e: MouseEvent) => {
		e.preventDefault();
		e.stopPropagation();
		onToggle(!favorite);
	}}
>
	<StarIcon
		class={cn('size-4', favorite ? 'fill-primary text-primary' : 'text-muted-foreground')}
	/>
</Button>
