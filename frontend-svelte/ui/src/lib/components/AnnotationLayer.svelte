<!--
	@component
	Pencil marks and text notes over one score page. Coordinates are page
	fractions (0..1) so marks stay put at any size. Drawing tools only take
	pointer input while a tool is selected; otherwise the layer is
	see-through and taps reach the viewer (page turns).
-->
<script lang="ts" module>
	export type Tool = 'pen' | 'text' | 'eraser' | null;

	// Once an Apple Pencil / stylus has been used, fingers no longer draw
	// (palm rejection) — they can still tap the toolbar.
	let stylusSeen = false;
</script>

<script lang="ts">
	import type { Annotation, AnnotationData, InkData, TextData } from '#lib/annotations.js';
	import * as m from '#lib/paraglide/messages.js';

	let {
		width,
		height,
		items,
		tool,
		color,
		onCreate,
		onUpdate,
		onDelete
	}: {
		width: number;
		height: number;
		items: Annotation[];
		tool: Tool;
		color: string;
		onCreate: (data: AnnotationData) => void;
		onUpdate: (id: number, data: AnnotationData) => void;
		onDelete: (id: number) => void;
	} = $props();

	const PEN_WIDTH = 0.004;
	const MIN_STEP = 0.0015;

	let root: HTMLDivElement | undefined = $state();
	let stroke: [number, number][] | null = $state(null);
	// Bookkeeping for one eraser drag, never rendered.
	// eslint-disable-next-line svelte/prefer-svelte-reactivity
	let erased = new Set<number>();
	let erasing = false;
	let editing: { id: number | null; x: number; y: number; text: string; color: string } | null =
		$state(null);

	let inks = $derived(
		items.filter((a) => a.data.kind === 'ink') as (Annotation & { data: InkData })[]
	);
	let notes = $derived(
		items.filter((a) => a.data.kind === 'text') as (Annotation & { data: TextData })[]
	);
	let fontSize = $derived(Math.max(11, width * 0.028));

	function toPage(e: PointerEvent): [number, number] {
		const rect = root!.getBoundingClientRect();
		const clamp = (v: number) => Math.min(1, Math.max(0, v));
		return [
			clamp((e.clientX - rect.left) / rect.width),
			clamp((e.clientY - rect.top) / rect.height)
		];
	}

	function polyline(points: [number, number][]) {
		return points.map(([x, y]) => `${(x * width).toFixed(1)},${(y * height).toFixed(1)}`).join(' ');
	}

	function annotationIdAt(e: PointerEvent): number | null {
		const el = document.elementFromPoint(e.clientX, e.clientY)?.closest('[data-annotation-id]');
		if (!el || !root?.contains(el)) return null;
		return Number(el.getAttribute('data-annotation-id'));
	}

	function eraseAt(e: PointerEvent) {
		const id = annotationIdAt(e);
		if (id !== null && !erased.has(id)) {
			erased.add(id);
			onDelete(id);
		}
	}

	function onPointerDown(e: PointerEvent) {
		if (!tool || !e.isPrimary) return;
		if ((e.target as Element).closest('textarea')) return;
		if (e.pointerType === 'pen') stylusSeen = true;

		if (tool === 'pen') {
			if (e.pointerType === 'touch' && stylusSeen) return;
			e.preventDefault();
			try {
				root!.setPointerCapture(e.pointerId);
			} catch {
				// Synthetic or already-released pointer: drawing still works.
			}
			stroke = [toPage(e)];
		} else if (tool === 'eraser') {
			e.preventDefault();
			erasing = true;
			erased = new Set();
			eraseAt(e);
		} else if (tool === 'text') {
			e.preventDefault();
			if (editing) {
				commit();
				return;
			}
			const id = annotationIdAt(e);
			const existing = id !== null ? notes.find((n) => n.id === id) : undefined;
			if (existing) {
				editing = { id: existing.id, ...existing.data };
			} else {
				const [x, y] = toPage(e);
				editing = { id: null, x, y, text: '', color };
			}
		}
	}

	function onPointerMove(e: PointerEvent) {
		if (stroke) {
			const events = e.getCoalescedEvents?.() ?? [e];
			for (const ev of events.length ? events : [e]) {
				const point = toPage(ev);
				const last = stroke[stroke.length - 1];
				if (Math.hypot(point[0] - last[0], point[1] - last[1]) >= MIN_STEP) {
					stroke.push(point);
				}
			}
		} else if (erasing) {
			eraseAt(e);
		}
	}

	function onPointerUp() {
		if (stroke) {
			const points = stroke.length === 1 ? [stroke[0], stroke[0]] : stroke.slice(0, 5000);
			onCreate({ kind: 'ink', points, color, width: PEN_WIDTH });
			stroke = null;
		}
		erasing = false;
	}

	function commit() {
		const current = editing;
		if (!current) return;
		editing = null;
		const text = current.text.trim().slice(0, 2000);
		const data: TextData = { kind: 'text', x: current.x, y: current.y, text, color: current.color };
		if (current.id === null) {
			if (text) onCreate(data);
		} else if (text) {
			const before = notes.find((n) => n.id === current.id)?.data;
			if (before?.text !== text) onUpdate(current.id, data);
		} else {
			onDelete(current.id);
		}
	}

	function onEditorKeydown(e: KeyboardEvent) {
		e.stopPropagation();
		if (e.key === 'Escape') {
			editing = null;
		} else if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			commit();
		}
	}

	function autofocus(el: HTMLTextAreaElement) {
		el.focus();
	}

	// Leaving text mode saves the note being written.
	$effect(() => {
		if (tool !== 'text') commit();
	});
</script>

<div
	bind:this={root}
	class={['absolute inset-0', tool ? 'touch-none' : 'pointer-events-none']}
	class:cursor-crosshair={tool === 'pen'}
	class:cursor-text={tool === 'text'}
	class:cursor-cell={tool === 'eraser'}
	role="presentation"
	onpointerdown={onPointerDown}
	onpointermove={onPointerMove}
	onpointerup={onPointerUp}
	onpointercancel={onPointerUp}
>
	<svg class="absolute inset-0 h-full w-full" viewBox="0 0 {width} {height}" aria-hidden="true">
		{#each inks as ink (ink.id)}
			<polyline
				points={polyline(ink.data.points)}
				fill="none"
				stroke={ink.data.color}
				stroke-width={Math.max(1, ink.data.width * width)}
				stroke-linecap="round"
				stroke-linejoin="round"
				opacity="0.85"
			/>
			{#if tool === 'eraser'}
				<polyline
					data-annotation-id={ink.id}
					points={polyline(ink.data.points)}
					fill="none"
					stroke="transparent"
					stroke-width={Math.max(16, ink.data.width * width * 4)}
					stroke-linecap="round"
					pointer-events="stroke"
				/>
			{/if}
		{/each}
		{#if stroke}
			<polyline
				points={polyline(stroke)}
				fill="none"
				stroke={color}
				stroke-width={Math.max(1, PEN_WIDTH * width)}
				stroke-linecap="round"
				stroke-linejoin="round"
				opacity="0.85"
			/>
		{/if}
	</svg>

	{#each notes as note (note.id)}
		{#if editing?.id !== note.id}
			<div
				data-annotation-id={note.id}
				class={[
					'absolute max-w-[45%] rounded-sm border-l-2 bg-yellow-100/90 px-1 py-0.5 leading-tight break-words whitespace-pre-wrap shadow-sm',
					tool ? 'pointer-events-auto' : 'pointer-events-none'
				]}
				style:left="{note.data.x * 100}%"
				style:top="{note.data.y * 100}%"
				style:color={note.data.color}
				style:border-color={note.data.color}
				style:font-size="{fontSize}px"
			>
				{note.data.text}
			</div>
		{/if}
	{/each}

	{#if editing}
		<textarea
			{@attach autofocus}
			bind:value={editing.text}
			placeholder={m.note_placeholder()}
			aria-label={m.tool_text()}
			maxlength="2000"
			rows="3"
			class="absolute z-10 w-[40%] min-w-40 resize-none rounded-sm border-2 bg-yellow-50 p-1 leading-tight text-neutral-900 shadow-md outline-none"
			style:left="{Math.min(editing.x, 0.6) * 100}%"
			style:top="{Math.min(editing.y, 0.85) * 100}%"
			style:border-color={editing.color}
			style:font-size="{Math.max(12, fontSize)}px"
			onkeydown={onEditorKeydown}
			onblur={commit}></textarea>
	{/if}
</div>
