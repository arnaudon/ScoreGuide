import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { callBackend } from './callBackend.js';

const text =
	(body: string, status = 200) =>
	async () =>
		new Response(body, { status });

describe('callBackend', () => {
	let errSpy: ReturnType<typeof vi.spyOn>;
	beforeEach(() => {
		errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
	});
	afterEach(() => errSpy.mockRestore());

	it('returns the parsed JSON object', async () => {
		const answer = await callBackend(text('{"detail":"x"}', 400));
		expect(answer?.res.status).toBe(400);
		expect(answer?.data).toEqual({ detail: 'x' });
	});

	it('gives {} for an empty body or a JSON value that is not an object', async () => {
		expect((await callBackend(async () => new Response(null, { status: 204 })))?.data).toEqual({});
		expect((await callBackend(text('')))?.data).toEqual({});
		expect((await callBackend(text('[1]')))?.data).toEqual({});
		expect((await callBackend(text('null')))?.data).toEqual({});
	});

	it('returns null when the backend is unreachable', async () => {
		const answer = await callBackend(async () => {
			throw new TypeError('fetch failed');
		});
		expect(answer).toBeNull();
		expect(errSpy).toHaveBeenCalled();
	});

	it('returns null for a success or 5xx answer that is not JSON', async () => {
		expect(await callBackend(text('<html>'))).toBeNull();
		expect(await callBackend(text('Internal Server Error', 500))).toBeNull();
		expect(await callBackend(text('Bad Gateway', 502))).toBeNull();
	});

	it('keeps a 4xx answer with a non-JSON body', async () => {
		const answer = await callBackend(text('Too Many Requests', 429));
		expect(answer?.res.status).toBe(429);
		expect(answer?.data).toEqual({});
	});
});
