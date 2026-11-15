import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GET, POST, PUT, DELETE } from './+server.js';
import { makeCookies, makeFetch, event, jsonResponse } from '../../../../../test-helpers.js';

type Handler = typeof GET;

function call(
	handler: Handler,
	method: string,
	params: Record<string, string>,
	{
		cookies = makeCookies({ access_token: 'tok' }),
		fetch = makeFetch(async () => jsonResponse([])),
		query = '',
		body
	}: {
		cookies?: ReturnType<typeof makeCookies>;
		fetch?: ReturnType<typeof makeFetch>;
		query?: string;
		body?: string;
	} = {}
) {
	const url = new URL(`http://localhost/api/scores/x/annotations${query}`);
	const request = new Request(url, { method, body });
	return handler(event({ params, cookies, fetch, request, url }) as Parameters<Handler>[0]);
}

describe('/api/scores/:scoreId/annotations proxy', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('rejects missing tokens, bad ids and wrong methods without calling the backend', async () => {
		const fetch = makeFetch();
		expect(
			(await call(GET, 'GET', { scoreId: '1' }, { cookies: makeCookies(), fetch })).status
		).toBe(401);
		expect((await call(GET, 'GET', { scoreId: '../x' }, { fetch })).status).toBe(404);
		expect(
			(await call(PUT, 'PUT', { scoreId: '1', annotationId: 'x' }, { fetch, body: '{}' })).status
		).toBe(404);
		expect((await call(PUT, 'PUT', { scoreId: '1' }, { fetch, body: '{}' })).status).toBe(405);
		expect((await call(GET, 'GET', { scoreId: '1', annotationId: '2' }, { fetch })).status).toBe(
			405
		);
		expect(
			(await call(DELETE, 'DELETE', { scoreId: '1' }, { fetch, query: '?page=x' })).status
		).toBe(400);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('lists with the bearer token', async () => {
		const fetch = makeFetch(async () => jsonResponse([{ id: 1 }]));
		const res = await call(GET, 'GET', { scoreId: '7' }, { fetch });
		expect(res.status).toBe(200);
		expect(await res.json()).toEqual([{ id: 1 }]);
		expect(fetch.mock.calls[0][0]).toMatch(/\/scores\/7\/annotations$/);
		expect(new Headers(fetch.mock.calls[0][1]!.headers).get('Authorization')).toBe('Bearer tok');
	});

	it('forwards JSON bodies for create and update', async () => {
		const fetch = makeFetch(async () => jsonResponse({ id: 3 }, 201));
		const body = JSON.stringify({ page: 1, data: { kind: 'text', x: 0, y: 0, text: 'hi' } });
		const res = await call(POST, 'POST', { scoreId: '7' }, { fetch, body });
		expect(res.status).toBe(201);
		expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'POST', body });
		expect(new Headers(fetch.mock.calls[0][1]!.headers).get('Content-Type')).toBe(
			'application/json'
		);

		await call(PUT, 'PUT', { scoreId: '7', annotationId: '3' }, { fetch, body });
		expect(fetch.mock.calls[1][0]).toMatch(/\/scores\/7\/annotations\/3$/);
		expect(fetch.mock.calls[1][1]).toMatchObject({ method: 'PUT', body });
	});

	it('deletes one annotation, a page, or the whole score', async () => {
		const fetch = makeFetch(async () => new Response(null, { status: 204 }));
		expect(
			(await call(DELETE, 'DELETE', { scoreId: '7', annotationId: '3' }, { fetch })).status
		).toBe(204);
		await call(DELETE, 'DELETE', { scoreId: '7' }, { fetch, query: '?page=2' });
		await call(DELETE, 'DELETE', { scoreId: '7' }, { fetch });
		expect(fetch.mock.calls.map((c) => c[0].replace(/^.*\/scores/, '/scores'))).toEqual([
			'/scores/7/annotations/3',
			'/scores/7/annotations?page=2',
			'/scores/7/annotations'
		]);
	});

	it('passes backend errors through and maps network errors to 500', async () => {
		const notFound = makeFetch(async () => jsonResponse({ detail: 'nope' }, 404));
		const res = await call(GET, 'GET', { scoreId: '7' }, { fetch: notFound });
		expect(res.status).toBe(404);
		expect(res.headers.get('Content-Type')).toBe('application/json');
		const down = makeFetch(async () => {
			throw new Error('down');
		});
		expect((await call(GET, 'GET', { scoreId: '7' }, { fetch: down })).status).toBe(500);
	});
});
