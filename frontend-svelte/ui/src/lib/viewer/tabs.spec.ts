import { describe, expect, it } from 'vitest';
import { closeTab, openTab, parseTabs, type ReaderTab } from './tabs';

const tab = (id: number, title = `S${id}`): ReaderTab => ({ id, title, composer: 'C' });

describe('openTab', () => {
	it('appends a new tab', () => {
		expect(openTab([tab(1)], tab(2)).map((t) => t.id)).toEqual([1, 2]);
	});

	it('keeps an open tab in place and refreshes its title', () => {
		const tabs = openTab([tab(1), tab(2)], tab(1, 'Renamed'));
		expect(tabs.map((t) => t.id)).toEqual([1, 2]);
		expect(tabs[0].title).toBe('Renamed');
	});

	it('drops the oldest past the limit', () => {
		expect(openTab([tab(1), tab(2), tab(3)], tab(4), 3).map((t) => t.id)).toEqual([2, 3, 4]);
	});
});

describe('closeTab', () => {
	const tabs = [tab(1), tab(2), tab(3)];

	it('moves to the right neighbour', () => {
		const { tabs: rest, next } = closeTab(tabs, 2);
		expect(rest.map((t) => t.id)).toEqual([1, 3]);
		expect(next?.id).toBe(3);
	});

	it('moves to the left neighbour when closing the last tab', () => {
		expect(closeTab(tabs, 3).next?.id).toBe(2);
	});

	it('has nothing left after the only tab', () => {
		expect(closeTab([tab(1)], 1)).toEqual({ tabs: [], next: null });
	});

	it('ignores an unknown id', () => {
		expect(closeTab(tabs, 9)).toEqual({ tabs, next: null });
	});
});

describe('parseTabs', () => {
	it('reads valid tabs and skips malformed ones', () => {
		const raw = JSON.stringify([tab(1), { id: 'x' }, null, tab(2)]);
		expect(parseTabs(raw).map((t) => t.id)).toEqual([1, 2]);
	});

	it('returns nothing for missing or broken data', () => {
		expect(parseTabs(null)).toEqual([]);
		expect(parseTabs('{oops')).toEqual([]);
		expect(parseTabs('{"id":1}')).toEqual([]);
	});
});
