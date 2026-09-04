import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isRedirect, isActionFailure } from '@sveltejs/kit';
import { load, actions } from './+page.server.js';
import { makeCookies, makeFetch, fakeRequest, jsonResponse, event } from '../test-helpers.js';

const USERS = [{ id: 1, username: 'alice', role: 'admin' }];
const STATS = { total_works: 100, total_composers: 50 };
const PROGRESS = { status: 'idle', page: 0, total: 0 };
const MODELS = {
	models: { main: 'gemini', imslp: 'gemini', complete: 'gemini', imslp_complete: 'gemini' }
};
const EMPTY_DEFAULTS = {
	users: [],
	stats: { total_works: 0, total_composers: 0 },
	progress: { status: 'idle', page: 0, total: 0 },
	activeModels: { main: '', imslp: '', complete: '', imslp_complete: '' }
};

describe('admin load', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('redirects to /login when no token', async () => {
		const fetch = vi.fn();
		await expect(load(event({ cookies: makeCookies(), fetch }))).rejects.toSatisfy(
			(t: unknown) => isRedirect(t) && t.location === '/login'
		);
	});

	it('redirects to / when /is_admin returns false', async () => {
		const fetch = vi.fn(async () => jsonResponse(false));
		await expect(
			load(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }))
		).rejects.toSatisfy((t: unknown) => isRedirect(t) && t.location === '/');
	});

	it('aggregates users/stats/progress/activeModels on the happy path', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse(true)) // /is_admin
			.mockResolvedValueOnce(jsonResponse(USERS)) // /users
			.mockResolvedValueOnce(jsonResponse(STATS)) // /imslp/stats
			.mockResolvedValueOnce(jsonResponse(PROGRESS)) // /imslp/progress
			.mockResolvedValueOnce(jsonResponse(MODELS)); // /admin/model
		const result = await load(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }));
		expect(result).toEqual({
			users: USERS,
			stats: STATS,
			progress: PROGRESS,
			activeModels: MODELS.models
		});
	});

	it('returns empty defaults when /users etc. all fail individually', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse(true))
			.mockResolvedValueOnce(new Response(null, { status: 500 }))
			.mockResolvedValueOnce(new Response(null, { status: 500 }))
			.mockResolvedValueOnce(new Response(null, { status: 500 }))
			.mockResolvedValueOnce(new Response(null, { status: 500 }));
		const result = await load(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }));
		expect(result).toEqual(EMPTY_DEFAULTS);
	});

	it('returns empty defaults and logs when fetch throws', async () => {
		const fetch = vi.fn().mockRejectedValueOnce(new Error('network'));
		const result = await load(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }));
		expect(result).toEqual(EMPTY_DEFAULTS);
		expect(errSpy).toHaveBeenCalled();
	});
});

describe('refill_credits action', () => {
	it('fails 400 when user_id is missing', async () => {
		const result = await actions.refill_credits(
			event({
				request: fakeRequest({}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 400 });
	});

	it('fails with backend status when the POST returns non-OK', async () => {
		const fetch = vi.fn(async () => jsonResponse({ detail: 'broke' }, 500));
		const result = await actions.refill_credits(
			event({
				request: fakeRequest({ user_id: '7' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toMatchObject({ status: 500, data: { error: 'broke' } });
	});

	it('returns undefined (no failure) when the POST is OK', async () => {
		const fetch = makeFetch();
		const result = await actions.refill_credits(
			event({
				request: fakeRequest({ user_id: '7' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toBeUndefined();
	});
});

describe('set_credits action', () => {
	it('fails 400 when fields are missing', async () => {
		const result = await actions.set_credits(
			event({
				request: fakeRequest({}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 400 });
	});

	it('posts max_credits as a number on happy path', async () => {
		const fetch = makeFetch();
		await actions.set_credits(
			event({
				request: fakeRequest({ user_id: '7', max_credits: '42' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		const body = JSON.parse(fetch.mock.calls[0][1]!.body as string);
		expect(body).toEqual({ max_credits: 42 });
	});
});

describe('set_models / update / empty / cancel actions', () => {
	it('set_models forwards the four model names', async () => {
		const fetch = makeFetch();
		await actions.set_models(
			event({
				request: fakeRequest({
					model_main: 'a',
					model_imslp: 'b',
					model_complete: 'c',
					model_imslp_complete: 'd'
				}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		const body = JSON.parse(fetch.mock.calls[0][1]!.body as string);
		expect(body).toEqual({ models: { main: 'a', imslp: 'b', complete: 'c', imslp_complete: 'd' } });
	});

	it('set_models returns success on the happy path', async () => {
		const fetch = makeFetch();
		const result = await actions.set_models(
			event({
				request: fakeRequest({ model_main: 'a' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toEqual({ formId: 'models', success: true });
	});

	it('set_models fails with the backend error when the save is rejected', async () => {
		const fetch = vi.fn(
			async () =>
				new Response(JSON.stringify({ detail: 'nope' }), {
					status: 400,
					headers: { 'Content-Type': 'application/json' }
				})
		);
		const result = await actions.set_models(
			event({
				request: fakeRequest({ model_main: 'a' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toMatchObject({ status: 400, data: { formId: 'models', error: 'nope' } });
	});

	it('update hits /imslp/start with the max_pages from the form (default 300)', async () => {
		const fetch = makeFetch();
		await actions.update(
			event({
				request: fakeRequest({}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(fetch.mock.calls[0][0]).toContain('/imslp/start/300');
	});

	it('empty action POSTs /imslp/empty', async () => {
		const fetch = makeFetch();
		await actions.empty(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }));
		expect(fetch.mock.calls[0][0]).toContain('/imslp/empty');
		expect(fetch.mock.calls[0][1]!.method).toBe('POST');
	});

	it('cancel action POSTs /imslp/cancel', async () => {
		const fetch = makeFetch();
		await actions.cancel(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }));
		expect(fetch.mock.calls[0][0]).toContain('/imslp/cancel');
	});
});
