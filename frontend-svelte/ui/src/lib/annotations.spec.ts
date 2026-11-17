import { describe, expect, it, vi } from 'vitest';
import { AnnotationsError, annotationsApi, localAnnotationsApi } from './annotations';

const ok = (body: unknown, status = 200) =>
	new Response(status === 204 ? null : JSON.stringify(body), { status });

describe('annotationsApi', () => {
	it('calls the same-origin proxy with JSON bodies', async () => {
		const fetchFn = vi.fn(async (_url: string, init?: RequestInit) =>
			init?.method === 'DELETE' ? ok(null, 204) : ok({ id: 1 })
		);
		const api = annotationsApi(5, fetchFn as unknown as typeof fetch);
		const ink = {
			kind: 'ink' as const,
			points: [[0, 0]] as [number, number][],
			color: '#000000',
			width: 0.004
		};

		await api.list();
		await api.create(2, ink);
		await api.update(1, 3, ink);
		expect(await api.remove(1)).toBeUndefined();
		await api.clearPage(4);

		expect(fetchFn.mock.calls.map(([u, i]) => `${i?.method ?? 'GET'} ${u}`)).toEqual([
			'GET /api/scores/5/annotations',
			'POST /api/scores/5/annotations',
			'PUT /api/scores/5/annotations/1',
			'DELETE /api/scores/5/annotations/1',
			'DELETE /api/scores/5/annotations?page=4'
		]);
		expect(JSON.parse(fetchFn.mock.calls[1][1]!.body as string)).toEqual({ page: 2, data: ink });
		expect(fetchFn.mock.calls[1][1]!.headers).toEqual({ 'Content-Type': 'application/json' });
	});

	it('throws with the status on failure', async () => {
		const api = annotationsApi(5, (async () => ok({}, 409)) as unknown as typeof fetch);
		await expect(
			api.create(1, { kind: 'text', x: 0, y: 0, text: 'x', color: '#000000' })
		).rejects.toEqual(new AnnotationsError(409));
	});
});

function memoryStorage(): Storage {
	const map = new Map<string, string>();
	return {
		get length() {
			return map.size;
		},
		clear: () => map.clear(),
		getItem: (k) => map.get(k) ?? null,
		key: (i) => [...map.keys()][i] ?? null,
		removeItem: (k) => void map.delete(k),
		setItem: (k, v) => void map.set(k, v)
	};
}

describe('localAnnotationsApi', () => {
	const text = (t: string) => ({
		kind: 'text' as const,
		x: 0.1,
		y: 0.2,
		text: t,
		color: '#000000'
	});

	it('creates, updates, removes and clears in browser storage, per score', async () => {
		const storage = memoryStorage();
		const api = localAnnotationsApi(7, storage);

		const a = await api.create(1, text('a'));
		const b = await api.create(2, text('b'));
		expect([a.id, b.id]).toEqual([1, 2]);
		expect(a).toMatchObject({ score_id: 7, page: 1, kind: 'text' });

		const updated = await api.update(a.id, 3, text('a2'));
		expect(updated).toMatchObject({ id: 1, page: 3, data: { text: 'a2' } });

		// Persisted: a fresh client on the same storage sees the same notes.
		expect((await localAnnotationsApi(7, storage).list()).map((n) => n.id)).toEqual([1, 2]);
		// Other scores are separate.
		expect(await localAnnotationsApi(8, storage).list()).toEqual([]);

		await api.clearPage(2);
		expect((await api.list()).map((n) => n.id)).toEqual([1]);
		await api.remove(1);
		expect(await api.list()).toEqual([]);
	});

	it('rejects updates of unknown notes like the server would', async () => {
		const api = localAnnotationsApi(7, memoryStorage());
		await expect(api.update(99, 1, text('x'))).rejects.toBeInstanceOf(AnnotationsError);
	});

	it('works without storage and ignores corrupt data', async () => {
		const api = localAnnotationsApi(7, null);
		await api.create(1, text('kept in memory'));
		expect(await api.list()).toHaveLength(1);

		const broken = memoryStorage();
		broken.setItem('demo.annotations.7', '{not json');
		expect(await localAnnotationsApi(7, broken).list()).toEqual([]);
		broken.setItem('demo.annotations.7', '{"not":"a list"}');
		expect(await localAnnotationsApi(7, broken).list()).toEqual([]);
	});

	it('keeps working when storage writes fail', async () => {
		const full = memoryStorage();
		full.setItem = () => {
			throw new Error('quota');
		};
		const api = localAnnotationsApi(7, full);
		await expect(api.create(1, text('x'))).resolves.toMatchObject({ id: 1 });
	});
});
