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

	it('sends the music profile only when the form has it ("" clears it)', async () => {
		const fetch = vi.fn(async () => jsonResponse({}));
		const send = (fields: Record<string, string>) =>
			actions.update_profile(
				event({
					request: fakeRequest(fields),
					cookies: makeCookies({ access_token: 'tok' }),
					fetch
				})
			);
		await send({ email: 'e@x', music_profile: 'Loves Debussy' });
		await send({ email: 'e@x', music_profile: '' });
		await send({ email: 'e@x' });
		const bodies = fetch.mock.calls.map((c) =>
			JSON.parse((c as unknown as [string, RequestInit])[1].body as string)
		);
		expect(bodies.map((b) => b.music_profile)).toEqual(['Loves Debussy', '', undefined]);
	});

	it('sends the detailed-descriptions preference only when the form has it', async () => {
		const fetch = vi.fn(async () => jsonResponse({}));
		for (const fields of [
			{ detailed_descriptions: 'true' },
			{ detailed_descriptions: 'false' },
			{}
		]) {
			await actions.update_profile(
				event({
					request: fakeRequest({ email: 'e@x', ...fields }),
					cookies: makeCookies({ access_token: 'tok' }),
					fetch
				})
			);
		}
		const bodies = fetch.mock.calls.map((c) =>
			JSON.parse((c as unknown as [string, RequestInit])[1].body as string)
		);
		expect(bodies.map((b) => b.detailed_descriptions)).toEqual([true, false, undefined]);
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
		new_password: 'new-password',
		confirm_password: 'new-password'
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

	it('fails 400 when the new password is too short', async () => {
		const fetch = vi.fn();
		const result = await actions.update_password(
			event({
				request: fakeRequest({ ...fields, new_password: 'short', confirm_password: 'short' }),
				cookies: makeCookies({ access_token: 'tok' }),
				fetch
			})
		);
		expect(result).toMatchObject({ status: 400, data: { form: 'password' } });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('returns success on happy path', async () => {
		const fetch = vi.fn(async () => jsonResponse({}));
		const result = await actions.update_password(
			event({ request: fakeRequest(fields), cookies: makeCookies({ access_token: 'tok' }), fetch })
		);
		expect(result).toEqual({ form: 'password', success: true });
	});

	it('keeps this session with the fresh token the backend returns', async () => {
		const fetch = vi.fn(async () => jsonResponse({ access_token: 'fresh' }));
		const cookies = makeCookies({ access_token: 'tok' });
		const result = await actions.update_password(
			event({ request: fakeRequest(fields), cookies, fetch })
		);
		expect(result).toEqual({ form: 'password', success: true });
		expect(cookies.set).toHaveBeenCalledWith('access_token', 'fresh', expect.any(Object));
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
