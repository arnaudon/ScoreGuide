import { describe, expect, it, vi } from 'vitest';
import { flushSync } from 'svelte';
import { AnnotationStore } from './annotations.svelte';
import type { Annotation, AnnotationData } from '#lib/annotations.js';

const note = (text: string): AnnotationData => ({
	kind: 'text',
	x: 0.1,
	y: 0.1,
	text,
	color: '#000000'
});

function fakeApi(overrides: Partial<Record<string, unknown>> = {}) {
	let nextId = 100;
	const saved = (page: number, data: AnnotationData, id = nextId++): Annotation => ({
		id,
		score_id: 1,
		page,
		kind: data.kind,
		data,
		created_at: '',
		updated_at: ''
	});
	return {
		list: vi.fn(async () => [saved(1, note('existing'), 1)]),
		create: vi.fn(async (page: number, data: AnnotationData) => saved(page, data)),
		update: vi.fn(async (id: number, page: number, data: AnnotationData) => saved(page, data, id)),
		remove: vi.fn(async () => undefined),
		clearPage: vi.fn(async () => undefined),
		...overrides
	};
}

const tick = () => new Promise((r) => setTimeout(r, 0));

describe('AnnotationStore', () => {
	it('loads, filters by page and reports load errors', async () => {
		const store = new AnnotationStore(fakeApi());
		await store.load();
		expect(store.loaded).toBe(true);
		expect(store.forPage(1).map((a) => a.id)).toEqual([1]);
		expect(store.forPage(2)).toEqual([]);

		const failing = new AnnotationStore(
			fakeApi({
				list: vi.fn(async () => {
					throw new Error('x');
				})
			})
		);
		await failing.load();
		expect(failing.error).toBe('load');
		failing.dismissError();
		expect(failing.error).toBeNull();
	});

	it('creates optimistically, then swaps in the saved id', async () => {
		const api = fakeApi();
		const store = new AnnotationStore(api);
		const temp = store.create(2, note('a'));
		expect(temp).toBeLessThan(0);
		expect(store.forPage(2)[0].id).toBe(temp);
		await tick();
		expect(store.forPage(2)[0].id).toBe(100);
		expect(api.create).toHaveBeenCalledWith(2, note('a'));
	});

	it('rolls back a failed create and flags the error', async () => {
		const store = new AnnotationStore(
			fakeApi({
				create: vi.fn(async () => {
					throw new Error('offline');
				})
			})
		);
		store.create(1, note('a'));
		await tick();
		expect(store.items).toEqual([]);
		expect(store.error).toBe('save');
	});

	it('removing an annotation still being saved deletes it once saved', async () => {
		const api = fakeApi();
		const store = new AnnotationStore(api);
		const temp = store.create(1, note('a'));
		await store.remove(temp);
		expect(store.items).toEqual([]);
		expect(api.remove).toHaveBeenCalledWith(100);
	});

	it('undoes create, delete and update', async () => {
		const api = fakeApi();
		const store = new AnnotationStore(api);
		await store.load();
		expect(store.canUndo).toBe(false);

		store.create(1, note('new'));
		await tick();
		await store.update(1, note('edited'));
		expect(store.items.find((a) => a.id === 1)?.data).toEqual(note('edited'));
		await store.remove(1);
		expect(store.items.map((a) => a.id)).toEqual([100]);
		flushSync();
		expect(store.canUndo).toBe(true);

		await store.undo(); // delete -> recreated
		await tick();
		expect(store.items.map((a) => (a.data as { text: string }).text)).toEqual(['new', 'edited']);

		await store.undo(); // update -> the recreated note goes back to "existing"
		expect(api.update).toHaveBeenLastCalledWith(101, 1, note('existing'));
		await store.undo(); // create -> removed
		expect(api.remove).toHaveBeenLastCalledWith(100);
		expect(store.items.map((a) => (a.data as { text: string }).text)).toEqual(['existing']);
		await store.undo(); // nothing left
		expect(store.canUndo).toBe(false);
	});

	it('restores state when a save fails', async () => {
		const api = fakeApi({
			update: vi.fn(async () => {
				throw new Error('x');
			}),
			remove: vi.fn(async () => {
				throw new Error('x');
			})
		});
		const store = new AnnotationStore(api);
		await store.load();
		await store.update(1, note('edited'));
		expect(store.items[0].data).toEqual(note('existing'));
		await store.remove(1);
		expect(store.items.map((a) => a.id)).toEqual([1]);
		expect(store.error).toBe('save');
	});
});
