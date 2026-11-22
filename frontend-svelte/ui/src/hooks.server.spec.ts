import { describe, expect, it, vi } from 'vitest';
import type { RequestEvent } from '@sveltejs/kit';
import { handleFetch } from './hooks.server';
import { BACKEND_URL } from '#lib/server/api.js';

async function run(url: string, headers: Record<string, string>, address: () => string) {
	const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response('ok'));
	const event = { getClientAddress: address } as unknown as RequestEvent;
	await handleFetch({ event, request: new Request(url, { headers }), fetch });
	return fetch.mock.calls[0][0] as Request;
}

describe('handleFetch', () => {
	it("forwards the visitor's address to the backend, replacing any sent one", async () => {
		const req = await run(`${BACKEND_URL}/token`, { 'X-Client-IP': 'forged' }, () => '203.0.113.9');
		expect(req.headers.get('X-Client-IP')).toBe('203.0.113.9');
	});

	it('drops a forged header when the address is unknown', async () => {
		const req = await run(`${BACKEND_URL}/token`, { 'X-Client-IP': 'forged' }, () => {
			throw new Error('no address');
		});
		expect(req.headers.has('X-Client-IP')).toBe(false);
	});

	it('leaves other requests alone', async () => {
		const req = await run('https://example.org/x', { 'X-Client-IP': 'kept' }, () => '1.2.3.4');
		expect(req.headers.get('X-Client-IP')).toBe('kept');
	});
});
