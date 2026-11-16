<script lang="ts" module>
	import * as m from '#lib/paraglide/messages.js';

	export const COLORS = [
		{ value: '#e11d48', label: () => m.color_red() },
		{ value: '#2563eb', label: () => m.color_blue() },
		{ value: '#16a34a', label: () => m.color_green() },
		{ value: '#171717', label: () => m.color_black() }
	];
</script>

<!--
	@component
	Annotation controls for the viewer toolbar: a pencil button that enters
	annotate mode, then pencil / note / eraser, colours, undo and done.
-->
<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Eraser from '@lucide/svelte/icons/eraser';
	import Pencil from '@lucide/svelte/icons/pencil';
	import StickyNote from '@lucide/svelte/icons/sticky-note';
	import Undo2 from '@lucide/svelte/icons/undo-2';
	import type { Tool } from './AnnotationLayer.svelte';
	import { isTypingTarget } from '#lib/viewer/layout.js';

	let {
		tool = $bindable(null),
		color = $bindable(COLORS[0].value),
		canUndo,
		onUndo
	}: {
		tool?: Tool;
		color?: string;
		canUndo: boolean;
		onUndo: () => void;
	} = $props();

	const btn =
		'inline-flex size-10 items-center justify-center rounded-full text-white transition-colors hover:bg-white/15 focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none disabled:opacity-40 aria-pressed:bg-white aria-pressed:text-neutral-900';

	function onKeydown(e: KeyboardEvent) {
		if (!tool || isTypingTarget(e.target, e.key)) return;
		if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
			e.preventDefault();
			onUndo();
		} else if (e.key === 'Escape') {
			tool = null;
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />

{#if !tool}
	<button
		type="button"
		class={btn}
		onclick={() => (tool = 'pen')}
		title={m.annotate()}
		aria-label={m.annotate()}
	>
		<Pencil class="size-5" />
	</button>
{:else}
	<div
		class="flex flex-wrap items-center justify-center gap-1"
		role="toolbar"
		aria-label={m.annotate()}
	>
		<button
			type="button"
			class={btn}
			aria-pressed={tool === 'pen'}
			onclick={() => (tool = 'pen')}
			title={m.tool_pen()}
			aria-label={m.tool_pen()}
		>
			<Pencil class="size-5" />
		</button>
		<button
			type="button"
			class={btn}
			aria-pressed={tool === 'text'}
			onclick={() => (tool = 'text')}
			title={m.tool_text()}
			aria-label={m.tool_text()}
		>
			<StickyNote class="size-5" />
		</button>
		<button
			type="button"
			class={btn}
			aria-pressed={tool === 'eraser'}
			onclick={() => (tool = 'eraser')}
			title={m.tool_eraser()}
			aria-label={m.tool_eraser()}
		>
			<Eraser class="size-5" />
		</button>
		{#each COLORS as swatch (swatch.value)}
			<button
				type="button"
				class="inline-flex size-8 items-center justify-center rounded-full focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none"
				aria-pressed={color === swatch.value}
				onclick={() => {
					color = swatch.value;
					if (tool === 'eraser') tool = 'pen';
				}}
				title={swatch.label()}
				aria-label={swatch.label()}
			>
				<span
					class={[
						'block size-5 rounded-full border-2',
						color === swatch.value ? 'border-white' : 'border-transparent'
					]}
					style:background-color={swatch.value}
				></span>
			</button>
		{/each}
		<button
			type="button"
			class={btn}
			onclick={onUndo}
			disabled={!canUndo}
			title={m.undo()}
			aria-label={m.undo()}
		>
			<Undo2 class="size-5" />
		</button>
		<button
			type="button"
			class={btn}
			onclick={() => (tool = null)}
			title={m.annotate_done()}
			aria-label={m.annotate_done()}
		>
			<Check class="size-5" />
		</button>
	</div>
{/if}
