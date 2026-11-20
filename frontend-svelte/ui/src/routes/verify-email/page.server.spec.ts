import { describe, expect, it, vi } from 'vitest';
import { isActionFailure } from '@sveltejs/kit';
import { actions, load } from './+page.server.js';

function cookies(token?: string) {
	return { get: vi.fn(() => token) };
}

const loadEvent = (url: string, fetch: ReturnType<typeof vi.fn>, token?: string) =>
	({ url: new URL(url), fetch, cookies: cookies(token) }) as never;

describe('verify-email load', () => {
	it('confirms a valid link', async () => {
		const fetch = vi.fn(async () => new Response('{}', { status: 200 }));
		const result = await load(loadEvent('http://x/verify-email?token=abc', fetch, 'tok'));
		expect(result).toEqual({ verified: true, loggedIn: true });
		const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
		expect(url).toMatch(/\/verify-email$/);
		expect(JSON.parse(init.body as string)).toEqual({ token: 'abc' });
	});

	it('reports an invalid or missing link', async () => {
		const fetch = vi.fn(async () => new Response('{}', { status: 400 }));
		expect(await load(loadEvent('http://x/verify-email?token=bad', fetch))).toEqual({
			verified: false,
			loggedIn: false
		});
		expect(await load(loadEvent('http://x/verify-email', fetch))).toEqual({
			verified: false,
			loggedIn: false
		});
		expect(fetch).toHaveBeenCalledTimes(1);
	});

	it('survives a backend outage', async () => {
		const err = vi.spyOn(console, 'error').mockImplementation(() => {});
		const fetch = vi.fn(async () => {
			throw new Error('down');
		});
		expect(await load(loadEvent('http://x/verify-email?token=t', fetch))).toEqual({
			verified: false,
			loggedIn: false
		});
		err.mockRestore();
	});
});

describe('resend action', () => {
	const event = (fetch: ReturnType<typeof vi.fn>, token?: string) =>
		({ fetch, cookies: cookies(token) }) as never;

	it('needs a login', async () => {
		const result = await actions.resend(event(vi.fn()));
		expect(isActionFailure(result)).toBe(true);
	});

	it('asks the backend to resend', async () => {
		const fetch = vi.fn(async () => new Response('{}', { status: 200 }));
		expect(await actions.resend(event(fetch, 'tok'))).toEqual({ resent: true });
		expect((fetch.mock.calls[0] as unknown as [string])[0]).toMatch(/\/resend-verification$/);
	});

	it('reports a failure (rate limit)', async () => {
		const fetch = vi.fn(async () => new Response('{}', { status: 429 }));
		const result = await actions.resend(event(fetch, 'tok'));
		expect(result).toMatchObject({ status: 429 });
	});
});
