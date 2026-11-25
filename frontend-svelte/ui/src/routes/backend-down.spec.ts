import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isActionFailure, isHttpError } from '@sveltejs/kit';
import { actions as login } from './login/+page.server.js';
import { actions as forgot } from './forgot-password/+page.server.js';
import { actions as reset } from './reset-password/+page.server.js';
import { actions as verify } from './verify-email/+page.server.js';
import { load as accountLoad, actions as account } from './account/+page.server.js';
import { makeCookies, fakeRequest, event } from './test-helpers.js';

const UNAVAILABLE = 'The service is temporarily unavailable. Please try again in a moment.';

/** The backend is down (fetch rejects) or answers a non-JSON page. */
const down = () =>
	vi.fn(async () => {
		throw new TypeError('fetch failed');
	});
const htmlPage = () => vi.fn(async () => new Response('<html>oops</html>', { status: 200 }));

describe('auth actions when the backend is unavailable', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	const cases: [string, (fetch: ReturnType<typeof vi.fn>) => unknown][] = [
		[
			'login',
			(fetch) =>
				login.login(
					event({
						request: fakeRequest({ username: 'u', password: 'p' }),
						cookies: makeCookies(),
						fetch
					})
				)
		],
		['demo', (fetch) => login.demo(event({ cookies: makeCookies(), fetch }))],
		[
			'register',
			(fetch) =>
				login.register(
					event({
						request: fakeRequest({ username: 'u', password: 'long-enough', email: 'e@x' }),
						cookies: makeCookies(),
						fetch
					})
				)
		],
		[
			'forgot-password',
			(fetch) => forgot.default(event({ request: fakeRequest({ email: 'e@x' }), fetch }))
		],
		[
			'reset-password',
			(fetch) =>
				reset.default(
					event({
						request: fakeRequest({
							token: 't',
							new_password: 'long-enough',
							confirm_password: 'long-enough'
						}),
						fetch
					})
				)
		],
		[
			'update_profile',
			(fetch) =>
				account.update_profile(
					event({
						request: fakeRequest({ email: 'e@x' }),
						cookies: makeCookies({ access_token: 'tok' }),
						fetch
					})
				)
		],
		[
			'update_password',
			(fetch) =>
				account.update_password(
					event({
						request: fakeRequest({
							current_password: 'old-password',
							new_password: 'long-enough',
							confirm_password: 'long-enough'
						}),
						cookies: makeCookies({ access_token: 'tok' }),
						fetch
					})
				)
		],
		[
			'delete_account',
			(fetch) =>
				account.delete_account(event({ cookies: makeCookies({ access_token: 'tok' }), fetch }))
		]
	];

	it.each(cases)('%s fails with 503 and a friendly message', async (_name, run) => {
		for (const fetch of [down(), htmlPage()]) {
			const result = await run(fetch);
			expect(isActionFailure(result)).toBe(true);
			expect(result).toMatchObject({ status: 503, data: { error: UNAVAILABLE } });
		}
	});

	it('resend verification fails with 503', async () => {
		const result = await verify.resend(
			event({ cookies: makeCookies({ access_token: 'tok' }), fetch: down() })
		);
		expect(result).toMatchObject({ status: 503, data: { resent: false } });
	});

	it('the account page shows the error page (503)', async () => {
		await expect(
			accountLoad(event({ cookies: makeCookies({ access_token: 'tok' }), fetch: down() }))
		).rejects.toSatisfy((e: unknown) => isHttpError(e) && e.status === 503);
	});
});
