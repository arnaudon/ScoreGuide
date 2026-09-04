import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isRedirect } from '@sveltejs/kit';
import { load, actions } from './+page.server.js';
import { makeCookies, makeFetch, fakeRequest, jsonResponse, event } from '../../test-helpers.js';

const SCORE = { id: 7, title: 'Sonata', composer: 'Beethoven' };

describe('reader/[id] load', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('redirects to /login when no token cookie', async () => {
		const fetch = vi.fn();
		const cookies = makeCookies();
		await expect(load(event({ cookies, fetch, params: { id: '7' } }))).rejects.toSatisfy(
			(thrown: unknown) => isRedirect(thrown) && thrown.location === '/login'
		);
		expect(fetch).not.toHaveBeenCalled();
	});

	it('fetches /scores/{id} directly and persists last_score_id when found', async () => {
		const fetch = makeFetch(async () => jsonResponse(SCORE));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: SCORE });
		expect(fetch.mock.calls[0][0]).toContain('/scores/7');
		expect(cookies.set).toHaveBeenCalledWith(
			'last_score_id',
			'7',
			expect.objectContaining({ httpOnly: true, sameSite: 'lax' })
		);
	});

	it('does not leak `token` into the page data', async () => {
		const fetch = vi.fn(async () => jsonResponse(SCORE));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = (await load(event({ cookies, fetch, params: { id: '7' } }))) as Record<
			string,
			unknown
		>;
		expect('token' in result).toBe(false);
	});

	it('returns score: null when the id is not found (404), and does NOT set last_score_id', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 404 }));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: null });
		expect(cookies.set).not.toHaveBeenCalled();
	});

	it('returns score: null when /scores/{id} responds non-OK', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 500 }));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: null });
	});

	it('returns score: null and logs when fetch throws', async () => {
		const fetch = vi.fn(async () => {
			throw new Error('network down');
		});
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch, params: { id: '7' } }));
		expect(result).toEqual({ score: null });
		expect(errSpy).toHaveBeenCalled();
	});
});

describe('reader/[id] update_score action', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('fails 401 when not authenticated', async () => {
		const result = await actions.update_score(
			event({
				request: fakeRequest({ id: '7', title: 't' }),
				cookies: makeCookies(),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 401 });
	});

	it('fails 400 when id is missing', async () => {
		const result = await actions.update_score(
			event({
				request: fakeRequest({ title: 't' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 400 });
	});

	it('PUTs the submitted fields on happy path', async () => {
		const fetch = makeFetch().mockResolvedValueOnce(jsonResponse({ id: 7 }));
		const result = await actions.update_score(
			event({
				request: fakeRequest({
					id: '7',
					title: 'New',
					composer: 'C',
					year: '1900',
					period: 'Modernist',
					difficulty: 'easy'
				}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toEqual({ success: true, scoreUpdated: true });
		expect(fetch.mock.calls[0][1]!.method).toBe('PUT');
		expect(fetch.mock.calls[0][0]).toContain('/scores/7');
		const body = JSON.parse(fetch.mock.calls[0][1]!.body as string);
		expect(body).toMatchObject({
			title: 'New',
			composer: 'C',
			year: 1900,
			period: 'Modernist',
			difficulty: 'easy'
		});
	});

	it('forwards backend failure status', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 404 }));
		const result = await actions.update_score(
			event({
				request: fakeRequest({ id: '999', title: 't' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toMatchObject({ status: 404 });
	});
});
