import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GET } from './+server.js';
import { makeCookies, makeFetch, event } from '../../../test-helpers.js';

describe('GET /api/user/export', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('sends visitors without a session to the login page', async () => {
		const fetch = makeFetch();
		const res = await GET(event({ cookies: makeCookies(), fetch }));
		expect(res.status).toBe(303);
		expect(res.headers.get('Location')).toBe('/login');
		expect(fetch).not.toHaveBeenCalled();
	});

	it('sends an expired session to the login page', async () => {
		const fetch = makeFetch(async () => new Response('{}', { status: 401 }));
		const res = await GET(event({ cookies: makeCookies({ access_token: 'old' }), fetch }));
		expect(res.status).toBe(303);
	});

	it('forwards the token and streams the ZIP with its download name', async () => {
		const body = new ReadableStream({
			start(c) {
				c.enqueue(new TextEncoder().encode('PK'));
				c.close();
			}
		});
		const fetch = makeFetch(
			async () =>
				new Response(body, {
					headers: {
						'Content-Type': 'application/zip',
						'Content-Length': '2',
						'Content-Disposition': 'attachment; filename="scoreguide-export-a-2026-11-26.zip"',
						'X-Other': 'dropped'
					}
				})
		);
		const res = await GET(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }));
		const [url, init] = fetch.mock.calls[0];
		expect(url).toMatch(/\/user\/export$/);
		expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer tok');
		expect(res.status).toBe(200);
		expect(res.body).toBe(body);
		expect(res.headers.get('Content-Disposition')).toContain('scoreguide-export-a-2026-11-26.zip');
		expect(res.headers.get('Content-Type')).toBe('application/zip');
		expect(res.headers.has('X-Other')).toBe(false);
	});

	it('passes backend errors through (e.g. the rate limit)', async () => {
		const fetch = makeFetch(async () => new Response('{"error":"limit"}', { status: 429 }));
		const res = await GET(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }));
		expect(res.status).toBe(429);
	});

	it('answers 503 when the backend is down', async () => {
		const fetch = makeFetch(async () => {
			throw new Error('ECONNREFUSED');
		});
		const res = await GET(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }));
		expect(res.status).toBe(503);
	});
});
