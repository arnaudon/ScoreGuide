/**
 * Pure helpers for the score viewer: which pages are on screen, where a
 * page turn lands, how a tap/swipe/key maps to an action. Kept free of
 * DOM and pdf.js so they can be unit-tested in node.
 */

export type ViewerAction = 'next' | 'prev' | 'first' | 'last' | 'menu' | 'fullscreen';

/** Show two pages side by side (like an open music stand) on wide screens. */
export function isSpread(width: number, height: number, numPages: number): boolean {
	return numPages > 1 && width >= 700 && width > height * 1.1;
}

/** Pages displayed when `page` is the first visible page. */
export function visiblePages(page: number, numPages: number, spread: boolean): number[] {
	if (numPages < 1) return [];
	const first = clampPage(page, numPages);
	return spread && first < numPages ? [first, first + 1] : [first];
}

export function clampPage(page: number, numPages: number): number {
	if (!Number.isFinite(page)) return 1;
	return Math.min(Math.max(1, Math.round(page)), Math.max(1, numPages));
}

/** First visible page after turning forward. In spread mode the last
 * turn shows the final two pages rather than a lone last page. */
export function nextPage(page: number, numPages: number, spread: boolean): number {
	const last = spread ? Math.max(1, numPages - 1) : numPages;
	return Math.max(clampPage(page, numPages), Math.min(page + (spread ? 2 : 1), last));
}

export function prevPage(page: number, numPages: number, spread: boolean): number {
	return clampPage(page - (spread ? 2 : 1), numPages);
}

/** Scale that fits a page of `pageW`×`pageH` (PDF units) inside a slot. */
export function fitScale(pageW: number, pageH: number, slotW: number, slotH: number): number {
	if (pageW <= 0 || pageH <= 0 || slotW <= 0 || slotH <= 0) return 0;
	return Math.min(slotW / pageW, slotH / pageH);
}

/** Tap zones: left third goes back, right third goes forward, middle
 * toggles the controls. */
export function tapAction(x: number, width: number): ViewerAction {
	if (width <= 0) return 'menu';
	const ratio = x / width;
	if (ratio < 1 / 3) return 'prev';
	if (ratio > 2 / 3) return 'next';
	return 'menu';
}

/** A mostly-horizontal drag of at least 50px is a page turn. */
export function swipeAction(dx: number, dy: number): ViewerAction | null {
	if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy) * 1.5) return null;
	return dx < 0 ? 'next' : 'prev';
}

type KeyLike = Pick<KeyboardEvent, 'key' | 'shiftKey' | 'ctrlKey' | 'metaKey' | 'altKey'>;

/** Keyboard and Bluetooth page-turner pedals (which send arrows or
 * PageUp/PageDown). */
export function keyAction(e: KeyLike): ViewerAction | null {
	if (e.ctrlKey || e.metaKey || e.altKey) return null;
	switch (e.key) {
		case 'ArrowRight':
		case 'ArrowDown':
		case 'PageDown':
			return 'next';
		case ' ':
			return e.shiftKey ? 'prev' : 'next';
		case 'ArrowLeft':
		case 'ArrowUp':
		case 'PageUp':
			return 'prev';
		case 'Home':
			return 'first';
		case 'End':
			return 'last';
		case 'f':
		case 'F':
			return 'fullscreen';
		default:
			return null;
	}
}

/** Don't steal keys from form fields or open dialogs. Space/Enter on a
 * focused button or link keep their usual meaning (arrows still turn). */
export function isTypingTarget(target: EventTarget | null, key = ''): boolean {
	if (!target || typeof (target as Element).closest !== 'function') return false;
	const el = target as Element;
	if (
		el.closest(
			'input, textarea, select, [contenteditable=""], [contenteditable="true"], [role="dialog"]'
		)
	)
		return true;
	return (key === ' ' || key === 'Enter') && !!el.closest('button, a[href]');
}

/** Small LRU so rendered pages stay around for instant back-and-forth
 * without holding every page of a long score in memory. */
export class LruCache<K, V> {
	#map = new Map<K, V>();
	constructor(private readonly max: number) {}

	get(key: K): V | undefined {
		const value = this.#map.get(key);
		if (value !== undefined) {
			this.#map.delete(key);
			this.#map.set(key, value);
		}
		return value;
	}

	set(key: K, value: V): void {
		this.#map.delete(key);
		this.#map.set(key, value);
		while (this.#map.size > this.max) {
			const oldest = this.#map.keys().next().value as K;
			this.#map.delete(oldest);
		}
	}

	clear(): void {
		this.#map.clear();
	}

	get size(): number {
		return this.#map.size;
	}
}
