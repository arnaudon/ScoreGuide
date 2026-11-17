import { describe, expect, it } from 'vitest';
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
	visiblePages
} from './layout';

const key = (k: string, mods: Partial<KeyboardEvent> = {}) => ({
	key: k,
	shiftKey: false,
	ctrlKey: false,
	metaKey: false,
	altKey: false,
	...mods
});

describe('layout', () => {
	it('uses spreads only on wide screens with several pages', () => {
		expect(isSpread(1200, 800, 10)).toBe(true);
		expect(isSpread(1200, 800, 1)).toBe(false);
		expect(isSpread(800, 1200, 10)).toBe(false);
		expect(isSpread(650, 400, 10)).toBe(false);
	});

	it('computes visible pages', () => {
		expect(visiblePages(1, 0, false)).toEqual([]);
		expect(visiblePages(3, 10, false)).toEqual([3]);
		expect(visiblePages(3, 10, true)).toEqual([3, 4]);
		expect(visiblePages(10, 10, true)).toEqual([10]);
		expect(visiblePages(99, 10, false)).toEqual([10]);
	});

	it('clamps pages', () => {
		expect(clampPage(0, 5)).toBe(1);
		expect(clampPage(7, 5)).toBe(5);
		expect(clampPage(Number.NaN, 5)).toBe(1);
		expect(clampPage(2.6, 5)).toBe(3);
	});

	it('turns pages forward and back', () => {
		expect(nextPage(1, 5, false)).toBe(2);
		expect(nextPage(5, 5, false)).toBe(5);
		expect(nextPage(1, 5, true)).toBe(3);
		expect(nextPage(3, 5, true)).toBe(4);
		expect(nextPage(4, 5, true)).toBe(4);
		expect(prevPage(3, 5, false)).toBe(2);
		expect(prevPage(3, 5, true)).toBe(1);
		expect(prevPage(1, 5, true)).toBe(1);
	});

	it('fits pages in their slot', () => {
		expect(fitScale(100, 200, 300, 300)).toBe(1.5);
		expect(fitScale(200, 100, 300, 300)).toBe(1.5);
		expect(fitScale(0, 100, 300, 300)).toBe(0);
	});

	it('maps taps and swipes', () => {
		expect(tapAction(10, 300)).toBe('prev');
		expect(tapAction(150, 300)).toBe('menu');
		expect(tapAction(290, 300)).toBe('next');
		expect(tapAction(5, 0)).toBe('menu');
		expect(swipeAction(-80, 10)).toBe('next');
		expect(swipeAction(80, 10)).toBe('prev');
		expect(swipeAction(30, 0)).toBeNull();
		expect(swipeAction(60, 60)).toBeNull();
		// Top-left corner and a swipe in from the left edge open the contents.
		expect(tapAction(10, 300, 20, 400)).toBe('contents');
		expect(tapAction(10, 300, 200, 400)).toBe('prev');
		expect(tapAction(290, 300, 20, 400)).toBe('next');
		expect(swipeAction(80, 10, 12)).toBe('contents');
		expect(swipeAction(80, 10, 200)).toBe('prev');
		expect(swipeAction(-80, 10, 12)).toBe('next');
	});

	it('maps keys, including pedal keys', () => {
		expect(keyAction(key('PageDown'))).toBe('next');
		expect(keyAction(key('ArrowRight'))).toBe('next');
		expect(keyAction(key(' '))).toBe('next');
		expect(keyAction(key(' ', { shiftKey: true }))).toBe('prev');
		expect(keyAction(key('PageUp'))).toBe('prev');
		expect(keyAction(key('Home'))).toBe('first');
		expect(keyAction(key('End'))).toBe('last');
		expect(keyAction(key('f'))).toBe('fullscreen');
		expect(keyAction(key('ArrowRight', { ctrlKey: true }))).toBeNull();
		expect(keyAction(key('x'))).toBeNull();
	});

	it('detects typing targets', () => {
		expect(isTypingTarget(null)).toBe(false);
		expect(isTypingTarget({} as EventTarget)).toBe(false);
		const fake = (matches: string[]) =>
			({
				closest: (sel: string) => (matches.some((m) => sel.includes(m)) ? {} : null)
			}) as unknown as Element;
		expect(isTypingTarget(fake(['textarea']))).toBe(true);
		expect(isTypingTarget(fake([]))).toBe(false);
		expect(isTypingTarget(fake(['button']), 'ArrowRight')).toBe(false);
		expect(isTypingTarget(fake(['button']), ' ')).toBe(true);
	});

	it('evicts least recently used entries', () => {
		const lru = new LruCache<number, string>(2);
		lru.set(1, 'a');
		lru.set(2, 'b');
		expect(lru.get(1)).toBe('a');
		lru.set(3, 'c');
		expect(lru.get(2)).toBeUndefined();
		expect(lru.get(1)).toBe('a');
		expect(lru.size).toBe(2);
		lru.clear();
		expect(lru.size).toBe(0);
	});
});
