import { describe, expect, it, vi } from 'vitest';
import { GET as health } from './health/+server.js';
import { GET as demoExample } from './demo-example/+server.js';

type Fetch = typeof fetch;
const call = (handler: (e: never) => unknown, fetch: Fetch) =>
	handler({ fetch } as never) as Promise<Response>;

describe('health', () => {
	it('is up only when the backend answers', async () => {
		const up = vi.fn(async () => new Response('{}', { status: 200 })) as unknown as Fetch;
		expect((await call(health, up)).status).toBe(200);
		const sick = vi.fn(async () => new Response('', { status: 500 })) as unknown as Fetch;
		expect((await call(health, sick)).status).toBe(503);
		const down = vi.fn(async () => {
			throw new TypeError('fetch failed');
		}) as unknown as Fetch;
		expect((await call(health, down)).status).toBe(503);
	});
});

describe('demo example', () => {
	it('passes only the description fields on', async () => {
		const body = { title: 'Prelude', long_description: '## History\nx', user_id: 3, extra: 1 };
		const ok = vi.fn(async () => Response.json(body)) as unknown as Fetch;
		const res = await call(demoExample, ok);
		const example = await res.json();
		expect(example.title).toBe('Prelude');
		expect(example.composer).toBe('');
		expect(example).not.toHaveProperty('user_id');
	});

	it('says when there is none', async () => {
		vi.spyOn(console, 'error').mockImplementation(() => {});
		const missing = vi.fn(async () => new Response('', { status: 404 })) as unknown as Fetch;
		expect((await call(demoExample, missing)).status).toBe(404);
		const broken = vi.fn(async () => new Response('', { status: 500 })) as unknown as Fetch;
		expect((await call(demoExample, broken)).status).toBe(502);
		const down = vi.fn(async () => {
			throw new TypeError('fetch failed');
		}) as unknown as Fetch;
		expect((await call(demoExample, down)).status).toBe(503);
	});
});
