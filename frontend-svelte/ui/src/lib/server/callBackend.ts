/** A backend answer whose body was read: `data` is its JSON object (`{}` when empty or not an object). */
export type BackendAnswer = { res: Response; data: Record<string, unknown> };

/**
 * Run a backend call from a form action without letting it throw. Returns
 * `null` when the backend can't be reached, or answers a success or a 5xx with
 * a body that isn't JSON (a proxy error page, a crash): the action then fails
 * with a friendly "unavailable" message instead of SvelteKit's 500 page.
 * A 4xx with a non-JSON body still comes back, with `data = {}`, so the
 * caller keeps the status and shows its own fallback message.
 */
export async function callBackend(call: () => Promise<Response>): Promise<BackendAnswer | null> {
	let res: Response;
	let text: string;
	try {
		res = await call();
		text = await res.text();
	} catch (e) {
		console.error('Backend unreachable:', e);
		return null;
	}
	if (!text) return { res, data: {} };
	try {
		const parsed: unknown = JSON.parse(text);
		const data =
			parsed && typeof parsed === 'object' && !Array.isArray(parsed)
				? (parsed as Record<string, unknown>)
				: {};
		return { res, data };
	} catch {
		if (res.ok || res.status >= 500) {
			console.error(`Backend answered ${res.status} with a non-JSON body`);
			return null;
		}
		return { res, data: {} };
	}
}
