import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GET } from './+server.js';
import { makeCookies, makeFetch, jsonResponse, event } from '../../../test-helpers.js';

function get(search: string, cookies = makeCookies({ access_token: 'tok' }), fetch = makeFetch()) {
	const url = new URL(`http://localhost/api/imslp/search${search}`);
	return GET(event({ url, cookies, fetch }) as Parameters<typeof GET>[0]);
}

describe('GET /api/imslp/search', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('401s without a token, without calling the backend', async () => {
		const fetch = makeFetch();
		expect((await get('?q=chopin', makeCookies(), fetch)).status).toBe(401);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('forwards only the known parameters with the bearer token', async () => {
		const fetch = makeFetch(async () => jsonResponse({ total: 1, results: [] }));
		const res = await get('?q=chopin+nocturne&period=Romantic&evil=1&offset=20', undefined, fetch);
		expect(res.status).toBe(200);
		expect(await res.json()).toEqual({ total: 1, results: [] });
		const called = String(fetch.mock.calls[0][0]);
		expect(called).toContain('/imslp/search?q=chopin+nocturne&period=Romantic&offset=20');
		expect(called).not.toContain('evil');
		expect(new Headers(fetch.mock.calls[0][1]!.headers).get('Authorization')).toBe('Bearer tok');
	});

	it('passes backend errors through and reports an unreachable backend', async () => {
		const failing = makeFetch(async () => jsonResponse({ detail: 'bad' }, 422));
		expect((await get('?q=x', undefined, failing)).status).toBe(422);
		const broken = makeFetch(async () => new Response('not json', { status: 500 }));
		const res = await get('?q=x', undefined, broken);
		expect(res.status).toBe(500);
		expect(await res.json()).toEqual({});
		const down = makeFetch(async () => {
			throw new Error('down');
		});
		expect((await get('?q=x', undefined, down)).status).toBe(502);
	});
});
