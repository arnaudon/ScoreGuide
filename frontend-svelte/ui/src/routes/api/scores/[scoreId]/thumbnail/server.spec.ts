import { describe, expect, it, vi } from 'vitest';
import { GET } from './+server';

type Event = Parameters<typeof GET>[0];

function event(scoreId: string, fetch: typeof globalThis.fetch, token = 'tok'): Event {
	return { params: { scoreId }, cookies: { get: () => token }, fetch } as unknown as Event;
}

describe('GET /api/scores/:id/thumbnail', () => {
	it('streams the image with the session token', async () => {
		const fetch = vi.fn(async () => new Response('png', { headers: { 'Cache-Control': 'x' } }));
		const res = await GET(event('7', fetch));
		expect(res.headers.get('Content-Type')).toBe('image/png');
		expect(res.headers.get('Cache-Control')).toBe('x');
		expect(await res.text()).toBe('png');
		const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
		expect(url).toMatch(/\/scores\/7\/thumbnail$/);
		expect(new Headers(init.headers).get('Authorization')).toBe('Bearer tok');
	});

	it('rejects bad ids and missing sessions', async () => {
		const fetch = vi.fn();
		expect((await GET(event('..%2Fadmin', fetch))).status).toBe(404);
		expect((await GET(event('7', fetch, ''))).status).toBe(404);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('maps failures', async () => {
		const missing = vi.fn(async () => new Response('no', { status: 404 }));
		expect((await GET(event('7', missing))).status).toBe(404);
		const expired = vi.fn(async () => new Response('no', { status: 401 }));
		expect((await GET(event('7', expired))).status).toBe(401);
		const down = vi.fn(async () => {
			throw new Error('down');
		});
		vi.spyOn(console, 'error').mockImplementation(() => {});
		expect((await GET(event('7', down))).status).toBe(500);
	});
});
