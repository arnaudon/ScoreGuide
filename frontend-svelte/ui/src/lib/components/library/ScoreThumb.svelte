<script lang="ts">
	import MusicIcon from '@lucide/svelte/icons/music';
	import { cn } from '#lib/utils.js';

	/**
	 * A score's first page (made by the backend once its PDF is processed), or a
	 * plain placeholder while there is none.
	 */
	let { scoreId, hasPdf = true, class: className = '' } = $props<{
		scoreId: number;
		hasPdf?: boolean;
		class?: string;
	}>();
	let failed = $state(false);
</script>

<div
	class={cn(
		'bg-muted/60 relative aspect-[1/1.3] shrink-0 overflow-hidden rounded-sm border',
		className
	)}
	aria-hidden="true"
>
	{#if hasPdf && !failed}
		<img
			src="/api/scores/{scoreId}/thumbnail"
			alt=""
			loading="lazy"
			decoding="async"
			class="size-full object-cover object-top dark:opacity-90 dark:invert"
			onerror={() => (failed = true)}
		/>
	{:else}
		<div class="text-muted-foreground/60 flex size-full items-center justify-center">
			<MusicIcon class="size-1/3" />
		</div>
	{/if}
</div>
