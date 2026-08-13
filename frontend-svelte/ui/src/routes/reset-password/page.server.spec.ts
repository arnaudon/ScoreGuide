import { describe, it, expect, vi } from 'vitest';
import { isActionFailure } from '@sveltejs/kit';
import { actions, load } from './+page.server.js';

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

const event = (request: Request, fetch: ReturnType<typeof vi.fn>) => ({ request, fetch }) as never;

describe('reset-password load', () => {
	it('exposes the token query param', async () => {
		const url = new URL('https://example.com/reset-password?token=abc');
		const result = await load({ url } as never);
		expect(result).toEqual({ token: 'abc' });
	});

	it('defaults to an empty token when missing', async () => {
		const url = new URL('https://example.com/reset-password');
		const result = await load({ url } as never);
		expect(result).toEqual({ token: '' });
	});
});

describe('reset-password action', () => {
	it('fails 400 when token is missing', async () => {
		const fetch = vi.fn();
		const result = await actions.default(
			event(fakeRequest({ new_password: 'a', confirm_password: 'a' }), fetch)
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 400, data: { error: 'Missing or invalid reset link' } });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('fails 400 when a password field is missing', async () => {
		const fetch = vi.fn();
		const result = await actions.default(
			event(fakeRequest({ token: 't', new_password: 'a' }), fetch)
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 400, data: { error: 'Missing password' } });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('fails 400 when passwords do not match', async () => {
		const fetch = vi.fn();
		const result = await actions.default(
			event(fakeRequest({ token: 't', new_password: 'a', confirm_password: 'b' }), fetch)
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 400, data: { error: 'Passwords do not match' } });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('fails with backend status when the token is invalid', async () => {
		const fetch = vi.fn(async () => jsonResponse({ detail: 'Invalid or expired reset link' }, 400));
		const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
		const result = await actions.default(
			event(fakeRequest({ token: 't', new_password: 'a', confirm_password: 'a' }), fetch)
		);
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({
			status: 400,
			data: { error: 'Invalid or expired reset link' }
		});
		errSpy.mockRestore();
	});

	it('returns success on a valid reset', async () => {
		const fetch = vi.fn(async () => jsonResponse({ message: 'Password reset successfully' }));
		const result = await actions.default(
			event(fakeRequest({ token: 't', new_password: 'a', confirm_password: 'a' }), fetch)
		);
		expect(result).toMatchObject({ success: true, message: 'Password reset successfully' });
	});
});
