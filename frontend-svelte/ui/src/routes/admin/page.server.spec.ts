import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isRedirect, isActionFailure } from '@sveltejs/kit';
import { load, actions } from './+page.server.js';
import { makeCookies, makeFetch, fakeRequest, jsonResponse, event } from '../test-helpers.js';

const USERS = [{ id: 1, username: 'alice', role: 'admin' }];
const STATS = { total_works: 100, total_composers: 50 };
const PROGRESS = { status: 'idle', page: 0, total: 0 };
const MODELS = {
	models: { main: 'gemini', imslp: 'gemini', complete: 'gemini' }
};
const EMPTY_DEFAULTS = {
	users: [],
	stats: { total_works: 0, total_composers: 0 },
	progress: { status: 'idle', start: 0, works: 0, error: '' },
	activeModels: { main: '', imslp: '', complete: '' },
	credentials: null,
	tocReports: [],
	planSettings: null,
	usageNow: [],
	usageMonth: [],
	month: ''
};
const PLANS = {
	limits: { free: { ai_tokens: 1, storage_mb: 2 }, pro: { ai_tokens: 3, storage_mb: 4 } },
	weights: {}
};
const USAGE = [{ user_id: 1, username: 'alice', requests: 2, cost: 10 }];
const URL_ = (search = '') => new URL(`http://localhost/admin${search}`);
const CREDENTIALS = { google_api_key: { set: true, source: 'env', hint: '…abcd' } };
const REPORTS = [{ id: 1, score_title: 'WTC II', comment: 'no preludes' }];

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
			.mockResolvedValueOnce(jsonResponse(MODELS)) // /admin/model
			.mockResolvedValueOnce(jsonResponse(CREDENTIALS)) // /admin/credentials
			.mockResolvedValueOnce(jsonResponse(REPORTS)) // /admin/toc-reports
			.mockResolvedValueOnce(jsonResponse(PLANS)) // /admin/plans
			.mockResolvedValueOnce(jsonResponse(USAGE)); // /admin/usage
		const result = await load(
			event({ cookies: makeCookies({ access_token: 'tok' }), fetch, url: URL_('?month=bad') })
		);
		expect(result).toEqual({
			users: USERS,
			stats: STATS,
			progress: PROGRESS,
			activeModels: MODELS.models,
			credentials: CREDENTIALS,
			tocReports: REPORTS,
			planSettings: PLANS,
			usageNow: USAGE,
			usageMonth: USAGE,
			month: ''
		});
	});

	it('loads the usage of the month picked in the URL', async () => {
		const fetch = vi.fn(async (url: string) => {
			if (url.includes('/is_admin')) return jsonResponse(true);
			if (url.includes('/admin/usage?month=2026-01')) return jsonResponse([{ user_id: 9 }]);
			if (url.includes('/admin/usage')) return jsonResponse(USAGE);
			return new Response(null, { status: 500 });
		});
		const result = await load(
			event({ cookies: makeCookies({ access_token: 'tok' }), fetch, url: URL_('?month=2026-01') })
		);
		expect(result).toMatchObject({
			month: '2026-01',
			usageNow: USAGE,
			usageMonth: [{ user_id: 9 }]
		});

		const failingMonth = vi.fn(async (url: string) =>
			url.includes('/is_admin') ? jsonResponse(true) : new Response(null, { status: 500 })
		);
		const empty = await load(
			event({
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: failingMonth,
				url: URL_('?month=2026-01')
			})
		);
		expect(empty).toMatchObject({ month: '2026-01', usageMonth: [] });
	});

	it('returns empty defaults when /users etc. all fail individually', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse(true))
			.mockResolvedValueOnce(new Response(null, { status: 500 }))
			.mockResolvedValueOnce(new Response(null, { status: 500 }))
			.mockResolvedValueOnce(new Response(null, { status: 500 }))
			.mockResolvedValueOnce(new Response(null, { status: 500 }))
			.mockResolvedValueOnce(new Response(null, { status: 500 }))
			.mockResolvedValueOnce(new Response(null, { status: 500 }))
			.mockResolvedValueOnce(new Response(null, { status: 500 }))
			.mockResolvedValueOnce(new Response(null, { status: 500 }));
		const result = await load(
			event({ cookies: makeCookies({ access_token: 'tok' }), fetch, url: URL_() })
		);
		expect(result).toEqual(EMPTY_DEFAULTS);
	});

	it('returns empty defaults and logs when fetch throws', async () => {
		const fetch = vi.fn().mockRejectedValueOnce(new Error('network'));
		const result = await load(
			event({ cookies: makeCookies({ access_token: 'tok' }), fetch, url: URL_() })
		);
		expect(result).toEqual(EMPTY_DEFAULTS);
		expect(errSpy).toHaveBeenCalled();
	});
});

describe('set_user_plan action', () => {
	const call = (
		fields: Record<string, string>,
		fetch = makeFetch(),
		cookies = makeCookies({ access_token: 'tok' })
	) => actions.set_user_plan(event({ request: fakeRequest(fields), cookies, fetch }));

	it('fails 401 without a token and 400 on a bad user id or plan', async () => {
		expect(await call({ user_id: '7', plan: 'pro' }, makeFetch(), makeCookies())).toMatchObject({
			status: 401
		});
		expect(await call({ user_id: 'x', plan: 'pro' })).toMatchObject({ status: 400 });
		expect(await call({ user_id: '7', plan: 'gold' })).toMatchObject({ status: 400 });
	});

	it('sends the plan, with empty limits as null', async () => {
		const fetch = makeFetch();
		const result = await call(
			{ user_id: '7', plan: 'pro', ai_allowance: ' 500 ', storage_limit_mb: '' },
			fetch
		);
		expect(fetch.mock.calls[0][0]).toContain('/users/7/plan');
		expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({
			plan: 'pro',
			ai_allowance: 500,
			storage_limit_mb: null
		});
		expect(result).toEqual({ formId: 'plan', success: true });
	});

	it('surfaces backend errors', async () => {
		const fetch = makeFetch(async () => jsonResponse({ detail: 'nope' }, 422));
		expect(await call({ user_id: '7', plan: 'pro' }, fetch)).toMatchObject({
			status: 422,
			data: { formId: 'plan', error: 'nope' }
		});
		const broken = makeFetch(async () => new Response('x', { status: 500 }));
		expect(await call({ user_id: '7', plan: 'pro' }, broken)).toMatchObject({
			data: { error: 'Could not update the plan' }
		});
	});
});

describe('set_plans action', () => {
	const FIELDS = {
		free_ai_tokens: '100',
		free_storage_mb: '200',
		pro_ai_tokens: '300',
		pro_storage_mb: '400',
		weights: 'infomaniak:big = 5'
	};
	const call = (
		fields: Record<string, string>,
		fetch = makeFetch(),
		cookies = makeCookies({ access_token: 'tok' })
	) => actions.set_plans(event({ request: fakeRequest(fields), cookies, fetch }));

	it('sends limits and parsed weights', async () => {
		const fetch = makeFetch();
		expect(await call(FIELDS, fetch)).toEqual({ formId: 'plans', success: true });
		expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({
			limits: {
				free: { ai_tokens: 100, storage_mb: 200 },
				pro: { ai_tokens: 300, storage_mb: 400 }
			},
			weights: { 'infomaniak:big': 5 }
		});
	});

	it('refuses malformed weights, a missing token and backend errors', async () => {
		expect(await call({ ...FIELDS, weights: 'oops' })).toMatchObject({
			status: 400,
			data: { error: 'Write each line as model = number.' }
		});
		expect(await call(FIELDS, makeFetch(), makeCookies())).toMatchObject({ status: 401 });
		const fetch = makeFetch(async () => jsonResponse({ detail: 'bad limits' }, 422));
		expect(await call(FIELDS, fetch)).toMatchObject({
			status: 422,
			data: { formId: 'plans', error: 'bad limits' }
		});
		const broken = makeFetch(async () => new Response('x', { status: 500 }));
		expect(await call(FIELDS, broken)).toMatchObject({
			data: { error: 'Could not save the plans' }
		});
	});
});

describe('set_credentials action', () => {
	it('sends only typed values and requested clears', async () => {
		const fetch = makeFetch();
		const result = await actions.set_credentials(
			event({
				request: fakeRequest({
					google_api_key: '  AIza-new  ',
					infomaniak_api_key: '',
					infomaniak_product_id: '42',
					clear_infomaniak_api_key: 'on'
				}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(fetch.mock.calls[0][0]).toContain('/admin/credentials');
		expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({
			credentials: {
				google_api_key: 'AIza-new',
				infomaniak_api_key: '',
				infomaniak_product_id: '42'
			}
		});
		expect(result).toEqual({ formId: 'credentials', success: true });
	});

	it('fails when the backend refuses', async () => {
		const fetch = makeFetch().mockResolvedValueOnce(new Response(null, { status: 403 }));
		const result = await actions.set_credentials(
			event({ request: fakeRequest({}), cookies: makeCookies({ access_token: 'tok' }), fetch })
		);
		expect(isActionFailure(result)).toBe(true);
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
					model_complete: 'c'
				}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		const body = JSON.parse(fetch.mock.calls[0][1]!.body as string);
		expect(body).toEqual({ models: { main: 'a', imslp: 'b', complete: 'c' } });
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

	it('update resumes the sync, or restarts it when asked', async () => {
		const fetch = makeFetch();
		const run = (fields: Record<string, string>) =>
			actions.update(
				event({
					request: fakeRequest(fields),
					cookies: makeCookies({ access_token: 'tok' }),
					fetch
				})
			);
		await run({});
		await run({ restart: 'true' });
		expect(fetch.mock.calls[0][0]).toMatch(/\/imslp\/start$/);
		expect(fetch.mock.calls[1][0]).toContain('/imslp/start?restart=true');
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

describe('admin action failures are surfaced', () => {
	const failing = () =>
		makeFetch(async () => jsonResponse({ detail: 'A job is already running' }, 409));

	it.each(['update', 'empty', 'cancel'] as const)(
		'%s returns an imslp-tagged failure when the backend rejects it',
		async (name) => {
			const result = await actions[name](
				event({
					request: fakeRequest({}),
					cookies: makeCookies({ access_token: 'tok' }),
					fetch: failing()
				})
			);
			expect(result).toMatchObject({
				status: 409,
				data: { formId: 'imslp', error: 'A job is already running' }
			});
		}
	);

	it('falls back to a status message when the IMSLP error has no detail', async () => {
		const result = await actions.cancel(
			event({
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: makeFetch(async () => new Response('x', { status: 500 }))
			})
		);
		expect(result).toMatchObject({ data: { error: 'IMSLP request failed (500).' } });
	});
});

describe('resolve_toc_report action', () => {
	const form = (id?: string) => {
		const body = new FormData();
		if (id) body.set('id', id);
		return new Request('http://x/admin', { method: 'POST', body });
	};

	it('fails 400 without a numeric id', async () => {
		for (const id of [undefined, '../x']) {
			const result = await actions.resolve_toc_report(
				event({ request: form(id), cookies: makeCookies({ access_token: 'tok' }), fetch: vi.fn() })
			);
			expect(isActionFailure(result) && result.status).toBe(400);
		}
	});

	it('posts to the backend and relays its failure', async () => {
		const ok = vi.fn(async () => jsonResponse({ resolved: true }));
		const done = await actions.resolve_toc_report(
			event({ request: form('3'), cookies: makeCookies({ access_token: 'tok' }), fetch: ok })
		);
		expect(done).toBeUndefined();
		expect(String((ok.mock.calls[0] as unknown[])[0])).toContain('/admin/toc-reports/3/resolve');

		const bad = vi.fn(async () => new Response(null, { status: 404 }));
		const failed = await actions.resolve_toc_report(
			event({ request: form('3'), cookies: makeCookies({ access_token: 'tok' }), fetch: bad })
		);
		expect(isActionFailure(failed) && failed.status).toBe(404);
	});
});
