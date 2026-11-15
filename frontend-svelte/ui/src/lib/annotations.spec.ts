import { describe, expect, it, vi } from 'vitest';
import { AnnotationsError, annotationsApi } from './annotations';

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
