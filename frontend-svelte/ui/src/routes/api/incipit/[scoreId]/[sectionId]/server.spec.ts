import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GET } from './+server.js';
import { makeCookies, makeFetch, event } from '../../../../test-helpers.js';

function get(
	params: Record<string, string>,
	cookies = makeCookies({ access_token: 'tok' }),
	fetch = makeFetch()
) {
	return GET(event({ params, cookies, fetch }) as Parameters<typeof GET>[0]);
}

describe('GET /api/incipit/:scoreId/:sectionId', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('404s without a token or with non-numeric ids, without calling the backend', async () => {
		const fetch = makeFetch();
		expect((await get({ scoreId: '1', sectionId: '2' }, makeCookies(), fetch)).status).toBe(404);
		expect((await get({ scoreId: '1', sectionId: '../x' }, undefined, fetch)).status).toBe(404);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('proxies the image with the bearer token', async () => {
		const fetch = makeFetch(
			async () =>
				new Response('png-bytes', {
					headers: { 'Content-Type': 'image/png', 'Cache-Control': 'private, max-age=60' }
				})
		);
		const res = await get({ scoreId: '1', sectionId: '2' }, undefined, fetch);
		expect(res.status).toBe(200);
		expect(res.headers.get('Content-Type')).toBe('image/png');
		expect(res.headers.get('Cache-Control')).toBe('private, max-age=60');
		expect(await res.text()).toBe('png-bytes');
		expect(fetch.mock.calls[0][0]).toContain('/scores/1/sections/2/incipit');
		expect(new Headers(fetch.mock.calls[0][1]!.headers).get('Authorization')).toBe('Bearer tok');
	});

	it('maps backend errors to 401/404 and network errors to 500', async () => {
		const status = (s: number) => makeFetch(async () => new Response(null, { status: s }));
		expect((await get({ scoreId: '1', sectionId: '2' }, undefined, status(401))).status).toBe(401);
		expect((await get({ scoreId: '1', sectionId: '2' }, undefined, status(404))).status).toBe(404);
		const down = makeFetch(async () => {
			throw new Error('down');
		});
		expect((await get({ scoreId: '1', sectionId: '2' }, undefined, down)).status).toBe(500);
		expect(errSpy).toHaveBeenCalled();
	});
});
