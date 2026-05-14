import { vi } from 'vitest';

/** vi.fn() typed so `.mock.calls[i]` carries [url, init?] tuples. */
export function makeFetch(impl?: (url: string, init?: RequestInit) => Promise<Response>) {
	return vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(
		impl ?? (async () => new Response(null, { status: 200 }))
	);
}

export function makeCookies(initial: Record<string, string> = {}) {
	const store = new Map(Object.entries(initial));
	return {
		get: vi.fn((k: string) => store.get(k)),
		set: vi.fn((k: string, v: string) => {
			store.set(k, v);
		}),
		delete: vi.fn((k: string) => {
			store.delete(k);
		}),
		serialize: vi.fn(),
		getAll: vi.fn()
	};
}

export function fakeRequest(fields: Record<string, string | Blob> = {}) {
	const fd = new FormData();
	for (const [k, v] of Object.entries(fields)) fd.append(k, v);
	return { formData: async () => fd } as unknown as Request;
}

export function jsonResponse(body: unknown, status = 200) {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

export const event = (
	overrides: Partial<{
		request: Request;
		cookies: ReturnType<typeof makeCookies>;
		fetch: ReturnType<typeof vi.fn>;
		params: Record<string, string>;
		url: URL;
	}> = {}
) => overrides as never;
