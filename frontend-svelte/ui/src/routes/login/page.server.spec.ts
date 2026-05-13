import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { isRedirect, isActionFailure } from '@sveltejs/kit';
import { actions } from './+page.server.js';

function makeCookies() {
	return {
		get: vi.fn(),
		set: vi.fn(),
		delete: vi.fn(),
		serialize: vi.fn(),
		getAll: vi.fn()
	};
}

function fakeRequest(fields: Record<string, string>) {
	const fd = new FormData();
	for (const [k, v] of Object.entries(fields)) fd.append(k, v);
	return { formData: async () => fd } as unknown as Request;
}

function jsonResponse(body: unknown, status = 200) {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

const event = (
	request: Request,
	cookies: ReturnType<typeof makeCookies>,
	fetch: ReturnType<typeof vi.fn>
) => ({ request, cookies, fetch }) as never;

describe('login action', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('fails 400 when username is missing', async () => {
		const fetch = vi.fn();
		const cookies = makeCookies();
		const result = await actions.login(event(fakeRequest({ password: 'p' }), cookies, fetch));
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 400, data: { error: 'Missing username or password' } });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('fails 400 when password is missing', async () => {
		const fetch = vi.fn();
		const cookies = makeCookies();
		const result = await actions.login(event(fakeRequest({ username: 'u' }), cookies, fetch));
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 400 });
	});

	it('fails with backend status when /token returns non-OK', async () => {
		const fetch = vi.fn(async () => jsonResponse({ detail: 'bad creds' }, 401));
		const cookies = makeCookies();
		const result = await actions.login(
			event(fakeRequest({ username: 'u', password: 'wrong' }), cookies, fetch)
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 401, data: { error: 'bad creds' } });
		expect(cookies.set).not.toHaveBeenCalled();
	});

	it('sets cookie with 1-day maxAge and redirects when remember is absent', async () => {
		const fetch = vi.fn(async () => jsonResponse({ access_token: 'tok' }));
		const cookies = makeCookies();
		await expect(
			actions.login(event(fakeRequest({ username: 'u', password: 'p' }), cookies, fetch))
		).rejects.toSatisfy((thrown: unknown) => {
			if (!isRedirect(thrown)) return false;
			expect(thrown.status).toBe(303);
			expect(thrown.location).toBe('/home');
			return true;
		});
		const [name, value, opts] = cookies.set.mock.calls[0];
		expect(name).toBe('access_token');
		expect(value).toBe('tok');
		expect(opts).toMatchObject({ httpOnly: true, sameSite: 'lax', maxAge: 60 * 60 * 24 });
	});

	it('sets cookie with 30-day maxAge when remember=on', async () => {
		const fetch = vi.fn(async () => jsonResponse({ access_token: 'tok' }));
		const cookies = makeCookies();
		await expect(
			actions.login(
				event(fakeRequest({ username: 'u', password: 'p', remember: 'on' }), cookies, fetch)
			)
		).rejects.toSatisfy((thrown: unknown) => isRedirect(thrown));
		expect(cookies.set.mock.calls[0][2]).toMatchObject({ maxAge: 60 * 60 * 24 * 30 });
	});
});

describe('register action', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('fails 400 when email is missing', async () => {
		const fetch = vi.fn();
		const cookies = makeCookies();
		const result = await actions.register(
			event(fakeRequest({ username: 'u', password: 'p' }), cookies, fetch)
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 400 });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('auto-logs in and redirects on successful registration', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse({ id: 1 })) // POST /users
			.mockResolvedValueOnce(jsonResponse({ access_token: 'newtok' })); // POST /token
		const cookies = makeCookies();
		await expect(
			actions.register(
				event(fakeRequest({ username: 'u', password: 'p', email: 'e@x' }), cookies, fetch)
			)
		).rejects.toSatisfy((thrown: unknown) => isRedirect(thrown) && thrown.location === '/home');
		expect(cookies.set).toHaveBeenCalledWith('access_token', 'newtok', expect.any(Object));
	});

	it('returns success message when registration succeeds but auto-login fails', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(jsonResponse({ id: 1 })) // POST /users
			.mockResolvedValueOnce(jsonResponse({ detail: 'unverified' }, 400)); // POST /token
		const cookies = makeCookies();
		const result = await actions.register(
			event(fakeRequest({ username: 'u', password: 'p', email: 'e@x' }), cookies, fetch)
		);
		expect(result).toMatchObject({ success: true, username: 'u' });
		expect(cookies.set).not.toHaveBeenCalled();
	});

	it('logs when the backend error response is not parseable JSON', async () => {
		const fetch = vi.fn(
			async () =>
				new Response('plain-text-error', {
					status: 409,
					headers: { 'Content-Type': 'text/plain' }
				})
		);
		const cookies = makeCookies();
		const result = await actions.register(
			event(fakeRequest({ username: 'u', password: 'p', email: 'e@x' }), cookies, fetch)
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 409, data: { error: 'Registration failed' } });
		expect(errSpy).toHaveBeenCalled();
	});
});
