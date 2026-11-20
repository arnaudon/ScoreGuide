/**
 * A readable message from a backend error `detail`. Our own errors are
 * strings; FastAPI validation errors (422) are a list of objects — showing
 * those raw would print "[object Object]", so take the first message.
 */
export function detailMessage(detail: unknown, fallback: string): string {
	if (typeof detail === 'string' && detail) return detail;
	if (Array.isArray(detail)) {
		const first = detail[0] as { msg?: unknown } | undefined;
		if (first && typeof first.msg === 'string') return first.msg;
	}
	return fallback;
}
