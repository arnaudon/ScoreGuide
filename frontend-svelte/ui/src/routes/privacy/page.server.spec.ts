import { describe, it, expect } from 'vitest';
import { load } from './+page.server.js';
import { vendorName } from '#lib/vendors.js';
import { makeFetch, jsonResponse, event } from '../test-helpers.js';

describe('privacy load', () => {
	it('lists the models in use with readable vendors', async () => {
		const fetch = makeFetch(async () =>
			jsonResponse({ models: [{ name: 'Kimi-K2.6', vendor: 'moonshotai', host: 'infomaniak' }] })
		);
		expect(await load(event({ fetch }))).toEqual({
			models: [{ name: 'Kimi-K2.6', vendor: 'Moonshot AI', host: 'infomaniak' }]
		});
		expect(fetch.mock.calls[0][0]).toMatch(/\/ai-models$/);
	});

	it('renders without models when the backend is down or odd', async () => {
		const down = makeFetch(async () => {
			throw new Error('down');
		});
		expect(await load(event({ fetch: down }))).toEqual({ models: [] });
		const notOk = makeFetch(async () => new Response(null, { status: 500 }));
		expect(await load(event({ fetch: notOk }))).toEqual({ models: [] });
		const odd = makeFetch(async () => jsonResponse({ nope: 1 }));
		expect(await load(event({ fetch: odd }))).toEqual({ models: [] });
	});

	it('keeps an unknown vendor as is', () => {
		expect(vendorName('Qwen')).toBe('Qwen (Alibaba)');
		expect(vendorName('acme')).toBe('acme');
	});
});
