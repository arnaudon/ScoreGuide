import { describe, it, expect, vi } from 'vitest';
import { isActionFailure } from '@sveltejs/kit';
import { actions } from './+page.server.js';

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

describe('forgot-password action', () => {
	it('fails 400 when email is missing', async () => {
		const fetch = vi.fn();
		const result = await actions.default(event(fakeRequest({}), fetch));
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 400, data: { error: 'Missing email' } });
		expect(fetch).not.toHaveBeenCalled();
	});

	it('returns the generic backend message on success', async () => {
		const fetch = vi.fn(async () =>
			jsonResponse({ message: 'If that email is registered, a reset link has been sent.' })
		);
		const result = await actions.default(event(fakeRequest({ email: 'a@example.com' }), fetch));
		expect(result).toMatchObject({
			email: 'a@example.com',
			message: 'If that email is registered, a reset link has been sent.'
		});
	});

	it('fails with backend status when the request errors', async () => {
		const fetch = vi.fn(async () => jsonResponse({ detail: 'rate limited' }, 429));
		const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
		const result = await actions.default(event(fakeRequest({ email: 'a@example.com' }), fetch));
		expect(isActionFailure(result)).toBe(true);
		expect(result).toMatchObject({ status: 429, data: { error: 'rate limited' } });
		errSpy.mockRestore();
	});
});
