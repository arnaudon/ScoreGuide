<!--
	@component
	A music-stand style PDF viewer built on the pdf.js rendering engine only
	(no pdf.js viewer app): one page — or two side by side on wide screens —
	fitted to the available space, turned with taps, swipes, arrow keys or a
	Bluetooth page-turner pedal. Has its own full-screen mode that keeps the
	controls and the table of contents reachable, and pre-renders the next
	pages so turning is instant.

	The `overlay` snippet is drawn on top of every visible page at the
	page's displayed size, for annotations.
-->
<script lang="ts" module>
	import workerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url';

	type PdfJs = typeof import('pdfjs-dist/legacy/build/pdf.mjs');
	let pdfjsPromise: Promise<PdfJs> | undefined;

	// Loaded lazily and only in the browser: pdf.js needs DOM APIs and is
	// large, so pages without a score never pay for it.
	function loadPdfjs(): Promise<PdfJs> {
		pdfjsPromise ??= import('pdfjs-dist/legacy/build/pdf.mjs').then((lib) => {
			lib.GlobalWorkerOptions.workerSrc = workerUrl;
			return lib;
		});
		return pdfjsPromise;
	}

	export type PageOverlay = { page: number; width: number; height: number };
</script>

<script lang="ts">
	import { onMount, untrack, type Snippet } from 'svelte';
	import type { PDFDocumentLoadingTask, PDFDocumentProxy } from 'pdfjs-dist/legacy/build/pdf.mjs';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import ListIcon from '@lucide/svelte/icons/list';
	import Maximize from '@lucide/svelte/icons/maximize';
	import Minimize from '@lucide/svelte/icons/minimize';
	import XIcon from '@lucide/svelte/icons/x';
	import {
		LruCache,
		clampPage,
		fitScale,
		isSpread,
		isTypingTarget,
		keyAction,
		nextPage,
		prevPage,
		swipeAction,
		tapAction,
		visiblePages,
		type ViewerAction
	} from '#lib/viewer/layout.js';
	import * as m from '#lib/paraglide/messages.js';

	let {
		url,
		page = $bindable(0),
		storageKey,
		contents,
		overlay,
		tools,
		interactive = true,
		label = 'PDF'
	}: {
		/** Same-origin PDF URL (the auth cookie rides along). */
		url: string;
		/** First visible page (1-based); 0 = restore the last page read. */
		page?: number;
		/** localStorage key to remember the last page read. */
		storageKey?: string;
		/** Table of contents, shown in a drawer inside the viewer so it
		 * stays reachable in full screen. Receives a go-to-page callback. */
		contents?: Snippet<[(page: number) => void]>;
		/** Drawn over each visible page at its displayed size. */
		overlay?: Snippet<[PageOverlay]>;
		/** Extra controls added to the toolbar. */
		tools?: Snippet;
		/** When false, taps and swipes on the page don't turn it (e.g.
		 * while drawing). Keys and toolbar buttons still work. */
		interactive?: boolean;
		label?: string;
	} = $props();

	const GAP = 8;
	const MAX_DPR = 2.5;

	let root: HTMLDivElement | undefined = $state();
	let stageW = $state(0);
	let stageH = $state(0);

	let doc: PDFDocumentProxy | null = $state.raw(null);
	let numPages = $state(0);
	let progress = $state(0);
	let failed = $state(false);
	/** Size of each page in PDF units; page 1's size stands in until known. */
	let sizes: Record<number, { w: number; h: number }> = $state({});
	/** Rendered canvas currently shown for each visible page. */
	let shown: Record<number, HTMLCanvasElement> = $state.raw({});

	let nativeFs = $state(false);
	let pseudoFs = $state(false);
	let fullscreen = $derived(nativeFs || pseudoFs);
	let controlsShown = $state(true);
	let contentsOpen = $state(false);
	let controlsVisible = $derived(!fullscreen || controlsShown || contentsOpen);

	let spread = $derived(isSpread(stageW, stageH, numPages));
	let visible = $derived(visiblePages(page, numPages, spread));
	let slotW = $derived(visible.length ? (stageW - GAP * (visible.length - 1)) / visible.length : 0);
	let slotH = $derived(stageH);

	function cssSize(n: number) {
		const s = sizes[n] ?? sizes[1] ?? { w: 595, h: 842 };
		const scale = fitScale(s.w, s.h, slotW, slotH);
		return { width: Math.floor(s.w * scale), height: Math.floor(s.h * scale) };
	}

	// ---- document loading -------------------------------------------------

	const canvases = new LruCache<number, { key: string; canvas: HTMLCanvasElement }>(12);
	// Plain Map on purpose: bookkeeping only, never rendered.
	// eslint-disable-next-line svelte/prefer-svelte-reactivity
	const inflight = new Map<string, Promise<HTMLCanvasElement | null>>();

	// A page passed in by the parent applies to the first document only;
	// switching to another score starts from its own remembered page.
	let firstLoad = true;

	$effect(() => {
		const src = url;
		const requested = firstLoad ? untrack(() => page) : 0;
		firstLoad = false;
		let task: PDFDocumentLoadingTask | undefined;
		let cancelled = false;

		doc = null;
		numPages = 0;
		progress = 0;
		failed = false;
		sizes = {};
		shown = {};
		canvases.clear();
		inflight.clear();

		loadPdfjs()
			.then(async (pdfjs) => {
				if (cancelled) return;
				task = pdfjs.getDocument({
					url: src,
					// Fewer, larger range requests: each one goes through the
					// SvelteKit proxy, the backend and S3.
					rangeChunkSize: 1 << 20,
					wasmUrl: '/pdfjs/wasm/',
					standardFontDataUrl: '/pdfjs/standard_fonts/',
					cMapUrl: '/pdfjs/cmaps/',
					iccUrl: '/pdfjs/iccs/',
					enableXfa: false
				});
				task.onProgress = ({ loaded: done, total }: { loaded: number; total: number }) => {
					if (total) progress = Math.min(1, done / total);
				};
				const loaded = await task.promise;
				if (cancelled) return;
				const first = await loaded.getPage(1);
				const vp = first.getViewport({ scale: 1 });
				sizes = { 1: { w: vp.width, h: vp.height } };
				numPages = loaded.numPages;
				page = clampPage(requested || restorePage(), loaded.numPages);
				doc = loaded;
			})
			.catch((error) => {
				if (cancelled) return;
				console.error('Failed to load PDF', error);
				failed = true;
			});

		return () => {
			cancelled = true;
			// Destroying the loading task also tears down its document.
			void task?.destroy();
		};
	});

	function restorePage(): number {
		if (!storageKey) return 1;
		try {
			return Number(localStorage.getItem(storageKey)) || 1;
		} catch {
			return 1;
		}
	}

	$effect(() => {
		if (!storageKey || !numPages) return;
		try {
			localStorage.setItem(storageKey, String(page));
		} catch {
			// Not remembered; harmless.
		}
	});

	// ---- rendering --------------------------------------------------------

	async function render(n: number, w: number, h: number): Promise<HTMLCanvasElement | null> {
		const pdf = doc;
		if (!pdf || n < 1 || n > pdf.numPages || w <= 0 || h <= 0) return null;
		const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
		const key = `${Math.round(w)}x${Math.round(h)}@${dpr}`;
		const cached = canvases.get(n);
		if (cached?.key === key) return cached.canvas;

		const id = `${n}:${key}`;
		let job = inflight.get(id);
		if (!job) {
			job = (async () => {
				const pdfPage = await pdf.getPage(n);
				const base = pdfPage.getViewport({ scale: 1 });
				if (!sizes[n]) sizes[n] = { w: base.width, h: base.height };
				const scale = fitScale(base.width, base.height, w, h);
				const viewport = pdfPage.getViewport({ scale: scale * dpr });
				const canvas = document.createElement('canvas');
				canvas.width = Math.floor(viewport.width);
				canvas.height = Math.floor(viewport.height);
				canvas.className = 'block h-full w-full';
				await pdfPage.render({ canvas, viewport }).promise;
				if (doc !== pdf) return null;
				canvases.set(n, { key, canvas });
				return canvas;
			})().finally(() => inflight.delete(id));
			inflight.set(id, job);
		}
		return job;
	}

	// Render what's on screen first, then quietly pre-render the next two
	// turns and the previous one so page turns don't wait.
	$effect(() => {
		const pdf = doc;
		const pages = visible;
		const w = slotW;
		const h = slotH;
		const isSpreadView = spread;
		const current = page;
		if (!pdf || !pages.length || w <= 0 || h <= 0) return;
		let stale = false;

		(async () => {
			for (const n of pages) {
				try {
					const canvas = await render(n, w, h);
					if (stale) return;
					if (canvas) shown = { ...shown, [n]: canvas };
				} catch (error) {
					// Cancelled when the document is swapped/closed mid-render.
					if ((error as Error)?.name !== 'RenderingCancelledException') {
						console.error(`Failed to render page ${n}`, error);
					}
				}
			}
			const ahead1 = nextPage(current, pdf.numPages, isSpreadView);
			const ahead2 = nextPage(ahead1, pdf.numPages, isSpreadView);
			const behind = prevPage(current, pdf.numPages, isSpreadView);
			const upcoming = [ahead1, ahead2, behind].flatMap((p) =>
				visiblePages(p, pdf.numPages, isSpreadView)
			);
			for (const n of upcoming) {
				if (stale) return;
				await render(n, w, h).catch(() => null);
			}
		})();

		return () => {
			stale = true;
		};
	});

	function showCanvas(canvas: HTMLCanvasElement) {
		return (el: HTMLElement) => {
			el.replaceChildren(canvas);
		};
	}

	// ---- navigation -------------------------------------------------------

	export function goTo(target: number) {
		if (!numPages) return;
		page = clampPage(target, numPages);
		contentsOpen = false;
	}

	function act(action: ViewerAction) {
		switch (action) {
			case 'next':
				page = nextPage(page, numPages, spread);
				break;
			case 'prev':
				page = prevPage(page, numPages, spread);
				break;
			case 'first':
				page = 1;
				break;
			case 'last':
				page = spread ? Math.max(1, numPages - 1) : numPages;
				break;
			case 'menu':
				if (fullscreen) {
					// A mouse moving onto the page has just revealed the
					// controls; the click that follows shouldn't hide them.
					const justRevealed = performance.now() - revealedAt < 1000;
					controlsShown = justRevealed || !controlsShown;
					if (controlsShown) scheduleHide();
				}
				break;
			case 'fullscreen':
				void toggleFullscreen();
				break;
		}
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.defaultPrevented || !numPages) return;
		if (e.key === 'Escape' && pseudoFs) {
			pseudoFs = false;
			return;
		}
		if (isTypingTarget(e.target, e.key)) return;
		// Another overlay (dialog, sheet) is open on top of the page.
		if (document.querySelector('[role="dialog"][data-state="open"]')) return;
		const action = keyAction(e);
		if (!action) return;
		e.preventDefault();
		act(action);
	}

	let pointerStart: { x: number; y: number; t: number } | null = null;

	function onPointerDown(e: PointerEvent) {
		if (!interactive || !e.isPrimary) return;
		pointerStart = { x: e.clientX, y: e.clientY, t: e.timeStamp };
	}

	function onPointerUp(e: PointerEvent) {
		const start = pointerStart;
		pointerStart = null;
		if (!interactive || !start || !numPages) return;
		const dx = e.clientX - start.x;
		const dy = e.clientY - start.y;
		const swipe = swipeAction(dx, dy);
		if (swipe) return act(swipe);
		if (Math.hypot(dx, dy) < 10 && e.timeStamp - start.t < 600) {
			const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
			act(tapAction(e.clientX - rect.left, rect.width));
		}
	}

	// ---- full screen ------------------------------------------------------

	export async function toggleFullscreen() {
		if (fullscreen) {
			pseudoFs = false;
			if (document.fullscreenElement) await document.exitFullscreen().catch(() => {});
			return;
		}
		if (root?.requestFullscreen && document.fullscreenEnabled) {
			try {
				await root.requestFullscreen({ navigationUI: 'hide' });
				return;
			} catch {
				// Fall through to the CSS version (e.g. iPhone Safari).
			}
		}
		pseudoFs = true;
	}

	export function openContents() {
		contentsOpen = true;
	}

	let hideTimer: ReturnType<typeof setTimeout> | undefined;
	function scheduleHide() {
		clearTimeout(hideTimer);
		hideTimer = setTimeout(() => {
			if (!contentsOpen) controlsShown = false;
		}, 3000);
	}

	$effect(() => {
		if (fullscreen) {
			controlsShown = true;
			scheduleHide();
		}
		return () => clearTimeout(hideTimer);
	});

	let revealedAt = 0;
	function onPointerMove(e: PointerEvent) {
		if (fullscreen && e.pointerType === 'mouse') {
			if (!controlsShown) revealedAt = performance.now();
			controlsShown = true;
			scheduleHide();
		}
	}

	onMount(() => {
		const onFsChange = () => (nativeFs = !!root && document.fullscreenElement === root);
		document.addEventListener('fullscreenchange', onFsChange);

		// Keep the screen awake while reading — nobody wants the tablet to
		// go dark mid-piece.
		let lock: WakeLockSentinel | undefined;
		const requestLock = async () => {
			try {
				if (document.visibilityState === 'visible' && 'wakeLock' in navigator) {
					lock = await navigator.wakeLock.request('screen');
				}
			} catch {
				// Not allowed (battery saver…) — fine.
			}
		};
		void requestLock();
		document.addEventListener('visibilitychange', requestLock);

		return () => {
			document.removeEventListener('fullscreenchange', onFsChange);
			document.removeEventListener('visibilitychange', requestLock);
			void lock?.release().catch(() => {});
		};
	});

	let lastVisible = $derived(visible.length ? visible[visible.length - 1] : 0);
	const btn =
		'inline-flex size-10 items-center justify-center rounded-full text-white transition-colors hover:bg-white/15 focus-visible:ring-2 focus-visible:ring-white focus-visible:outline-none disabled:opacity-40';
</script>

<svelte:window onkeydown={onKeydown} />

<div
	bind:this={root}
	role="region"
	aria-label={label}
	class={[
		'relative flex h-full w-full flex-col overflow-hidden bg-neutral-200 select-none dark:bg-neutral-800',
		pseudoFs && 'fixed inset-0 z-50',
		fullscreen && 'bg-neutral-900 dark:bg-neutral-950'
	]}
	onpointermove={onPointerMove}
>
	<!-- Pages -->
	<div
		class="relative min-h-0 flex-1 touch-pan-y"
		onpointerdown={onPointerDown}
		onpointerup={onPointerUp}
		onpointercancel={() => (pointerStart = null)}
		role="presentation"
	>
		<!-- Absolutely positioned so its measured size never depends on the
		     pages inside it (which are sized from that measurement). -->
		<div
			class="absolute inset-2 flex items-center justify-center"
			style:gap="{GAP}px"
			bind:clientWidth={stageW}
			bind:clientHeight={stageH}
		>
			{#if failed}
				<p role="alert" class="text-destructive bg-card rounded-md px-4 py-3 text-sm font-medium">
					{m.viewer_load_error()}
				</p>
			{:else if !doc}
				<div role="status" class="text-muted-foreground flex flex-col items-center gap-3 text-sm">
					<div class="bg-muted h-1.5 w-48 overflow-hidden rounded-full">
						<div class="bg-primary h-full transition-[width]" style:width="{progress * 100}%"></div>
					</div>
					{m.viewer_loading()}
				</div>
			{:else}
				{#each visible as n (n)}
					{@const size = cssSize(n)}
					<div
						class="relative shrink-0 bg-white shadow-md"
						style:width="{size.width}px"
						style:height="{size.height}px"
						data-page={n}
					>
						{#if shown[n]}
							<div class="absolute inset-0" {@attach showCanvas(shown[n])}></div>
						{:else}
							<div class="absolute inset-0 animate-pulse bg-neutral-100"></div>
						{/if}
						{#if overlay}
							{@render overlay({ page: n, width: size.width, height: size.height })}
						{/if}
					</div>
				{/each}
			{/if}
		</div>
	</div>

	<!-- Exit button: always obvious in full screen -->
	{#if fullscreen && controlsVisible}
		<button
			type="button"
			class="absolute top-3 right-3 z-20 inline-flex items-center gap-2 rounded-full bg-black/70 px-4 py-2 text-sm font-medium text-white shadow-lg backdrop-blur hover:bg-black/85"
			onclick={() => toggleFullscreen()}
		>
			<XIcon class="size-4" />
			{m.viewer_exit_fullscreen()}
		</button>
	{/if}

	<!-- Toolbar -->
	<div
		class={[
			'pointer-events-none z-20 flex justify-center px-3 transition-opacity duration-300',
			// Below the pages normally; floating (and auto-hiding) in full
			// screen so the music gets the whole screen.
			fullscreen ? 'absolute inset-x-0 bottom-3' : 'shrink-0 pb-2',
			controlsVisible ? 'opacity-100' : 'opacity-0'
		]}
		inert={!controlsVisible}
	>
		<div
			class="pointer-events-auto flex max-w-full items-center gap-1 rounded-full bg-black/70 px-2 py-1 shadow-lg backdrop-blur"
		>
			{#if contents}
				<button
					type="button"
					class={btn}
					onclick={() => (contentsOpen = !contentsOpen)}
					aria-expanded={contentsOpen}
					title={m.toc_contents()}
					aria-label={m.toc_contents()}
				>
					<ListIcon class="size-5" />
				</button>
			{/if}
			<button
				type="button"
				class={btn}
				onclick={() => act('prev')}
				disabled={!numPages || page <= 1}
				title={m.viewer_prev_page()}
				aria-label={m.viewer_prev_page()}
			>
				<ChevronLeft class="size-5" />
			</button>
			<label class="flex items-center gap-2 px-1 text-sm text-white tabular-nums">
				<span class="sr-only">{m.viewer_go_to_page()}</span>
				<input
					type="range"
					min="1"
					max={Math.max(1, numPages)}
					value={page}
					disabled={numPages < 2}
					oninput={(e) => goTo(Number(e.currentTarget.value))}
					class="hidden w-28 accent-white sm:block md:w-40"
				/>
				<span class="whitespace-nowrap">
					{numPages
						? lastVisible > page
							? m.viewer_pages_of({ from: page, to: lastVisible, total: numPages })
							: m.viewer_page_of({ page, total: numPages })
						: '–'}
				</span>
			</label>
			<button
				type="button"
				class={btn}
				onclick={() => act('next')}
				disabled={!numPages || lastVisible >= numPages}
				title={m.viewer_next_page()}
				aria-label={m.viewer_next_page()}
			>
				<ChevronRight class="size-5" />
			</button>
			{#if tools}
				<span class="mx-1 h-6 w-px bg-white/30"></span>
				{@render tools()}
			{/if}
			<span class="mx-1 h-6 w-px bg-white/30"></span>
			<button
				type="button"
				class={btn}
				onclick={() => toggleFullscreen()}
				title={fullscreen ? m.viewer_exit_fullscreen() : m.viewer_fullscreen()}
				aria-label={fullscreen ? m.viewer_exit_fullscreen() : m.viewer_fullscreen()}
			>
				{#if fullscreen}<Minimize class="size-5" />{:else}<Maximize class="size-5" />{/if}
			</button>
		</div>
	</div>

	<!-- Contents drawer (inside the viewer so it works in full screen) -->
	{#if contents && contentsOpen}
		<button
			type="button"
			class="absolute inset-0 z-30 bg-black/30"
			aria-label={m.viewer_close()}
			onclick={() => (contentsOpen = false)}
		></button>
		<aside
			aria-label={m.toc_contents()}
			class="bg-card text-card-foreground absolute inset-y-0 left-0 z-40 flex w-80 max-w-[85%] flex-col shadow-xl"
		>
			<div class="flex items-center justify-between border-b px-4 py-3">
				<h2 class="font-semibold">{m.toc_contents()}</h2>
				<button
					type="button"
					class="hover:bg-accent inline-flex size-8 items-center justify-center rounded-md"
					aria-label={m.viewer_close()}
					onclick={() => (contentsOpen = false)}
				>
					<XIcon class="size-4" />
				</button>
			</div>
			<div class="min-h-0 flex-1 overflow-y-auto p-3">
				{@render contents(goTo)}
			</div>
		</aside>
	{/if}
</div>
