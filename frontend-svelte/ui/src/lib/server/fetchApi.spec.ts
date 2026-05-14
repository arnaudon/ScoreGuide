import { describe, it, expect, vi } from 'vitest';
import { apiFetch } from './fetchApi.js';
import { BACKEND_URL } from './api.js';

function makeFetch() {
	return vi.fn<typeof fetch>(async () => new Response(null, { status: 200 }));
}

describe('apiFetch', () => {
	it('prepends BACKEND_URL to the path', async () => {
		const fetch = makeFetch();
		await apiFetch(fetch, 'tok')('/scores');
		expect(fetch).toHaveBeenCalledWith(`${BACKEND_URL}/scores`, expect.any(Object));
	});

	it('attaches the bearer header when a token is provided', async () => {
		const fetch = makeFetch();
		await apiFetch(fetch, 'tok')('/user');
		const init = fetch.mock.calls[0][1];
		expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer tok');
	});

	it('omits the bearer header when token is undefined', async () => {
		const fetch = makeFetch();
		await apiFetch(fetch, undefined)('/health');
		const init = fetch.mock.calls[0][1];
		expect(new Headers(init?.headers).get('Authorization')).toBeNull();
	});

	it('preserves caller-supplied headers and method/body', async () => {
		const fetch = makeFetch();
		await apiFetch(fetch, 'tok')('/agent', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: '{}'
		});
		const init = fetch.mock.calls[0][1];
		const headers = new Headers(init?.headers);
		expect(init?.method).toBe('POST');
		expect(init?.body).toBe('{}');
		expect(headers.get('Content-Type')).toBe('application/json');
		expect(headers.get('Authorization')).toBe('Bearer tok');
	});

	it('lets caller override the Authorization header', async () => {
		const fetch = makeFetch();
		await apiFetch(fetch, 'tok')('/x', { headers: { Authorization: 'Bearer override' } });
		const init = fetch.mock.calls[0][1];
		expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer override');
	});
});
