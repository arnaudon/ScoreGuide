import { describe, it, expect, vi } from 'vitest';
import { isRedirect, isActionFailure } from '@sveltejs/kit';
import { load, actions } from './+page.server.js';
import { makeCookies, fakeRequest, jsonResponse, event } from '../test-helpers.js';

const USER = { id: 1, username: 'alice' };

describe('account load', () => {
	it('redirects to /login when no token', async () => {
		const fetch = vi.fn();
		const cookies = makeCookies();
		await expect(load(event({ cookies, fetch }))).rejects.toSatisfy(
			(t: unknown) => isRedirect(t) && t.location === '/login'
		);
	});

	it('redirects to /login when /user is non-OK', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 401 }));
		const cookies = makeCookies({ access_token: 'tok' });
		await expect(load(event({ cookies, fetch }))).rejects.toSatisfy(
			(t: unknown) => isRedirect(t) && t.location === '/login'
		);
	});

	it('returns the user on happy path', async () => {
		const fetch = vi.fn(async () => jsonResponse(USER));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await load(event({ cookies, fetch }));
		expect(result).toEqual({ user: USER });
	});
});

describe('update_profile action', () => {
	it('fails 401 when not authenticated', async () => {
		const fetch = vi.fn();
		const result = await actions.update_profile(
			event({ request: fakeRequest({ email: 'e@x' }), cookies: makeCookies(), fetch })
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 401 });
	});

	it('returns { form: "profile", success: true } on happy path', async () => {
		const fetch = vi.fn(async () => jsonResponse({}));
		const result = await actions.update_profile(
			event({
				request: fakeRequest({ email: 'e@x', instrument: 'piano' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toEqual({ form: 'profile', success: true });
		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining('/user'),
			expect.objectContaining({ method: 'PUT' })
		);
	});

	it('fails with backend detail when /user PUT returns non-OK', async () => {
		const fetch = vi.fn(async () => jsonResponse({ detail: 'taken' }, 409));
		const result = await actions.update_profile(
			event({
				request: fakeRequest({ email: 'e@x' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 409, data: { form: 'profile', error: 'taken' } });
	});
});

describe('update_password action', () => {
	const fields = {
		current_password: 'old',
		new_password: 'new',
		confirm_password: 'new'
	};

	it('fails 401 when not authenticated', async () => {
		const result = await actions.update_password(
			event({ request: fakeRequest(fields), cookies: makeCookies(), fetch: vi.fn() })
		);
		expect(result).toMatchObject({ status: 401 });
	});

	it('fails 400 when any field is missing', async () => {
		const result = await actions.update_password(
			event({
				request: fakeRequest({ current_password: 'old' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({ status: 400, data: { form: 'password' } });
	});

	it('fails 400 when new !== confirm', async () => {
		const result = await actions.update_password(
			event({
				request: fakeRequest({ ...fields, confirm_password: 'different' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch: vi.fn()
			})
		);
		expect(result).toMatchObject({
			status: 400,
			data: { error: 'New passwords do not match' }
		});
	});

	it('returns success on happy path', async () => {
		const fetch = vi.fn(async () => jsonResponse({}));
		const result = await actions.update_password(
			event({ request: fakeRequest(fields), cookies: makeCookies({ access_token: 'tok' }), fetch })
		);
		expect(result).toEqual({ form: 'password', success: true });
	});
});

describe('delete_account action', () => {
	it('fails 401 when not authenticated', async () => {
		const result = await actions.delete_account(
			event({ request: fakeRequest({}), cookies: makeCookies(), fetch: vi.fn() })
		);
		expect(result).toMatchObject({ status: 401 });
	});

	it('clears cookie and redirects to /login on happy path', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 200 }));
		const cookies = makeCookies({ access_token: 'tok' });
		await expect(
			actions.delete_account(event({ request: fakeRequest({}), cookies, fetch }))
		).rejects.toSatisfy((t: unknown) => isRedirect(t) && t.location === '/login');
		expect(cookies.delete).toHaveBeenCalledWith('access_token', expect.any(Object));
	});

	it('fails with backend status when /user DELETE returns non-OK', async () => {
		const fetch = vi.fn(async () => new Response(null, { status: 500 }));
		const result = await actions.delete_account(
			event({
				request: fakeRequest({}),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 500, data: { form: 'delete' } });
	});
});
