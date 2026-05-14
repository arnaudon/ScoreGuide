import { BACKEND_URL } from './api.js';

type FetchFn = typeof fetch;

export function apiFetch(fetch: FetchFn, token: string | undefined) {
	return (path: string, init: RequestInit = {}) => {
		// Caller-supplied Authorization wins — don't clobber it if a route
		// explicitly passes a different bearer (or wants to send the request
		// unauthenticated by setting an empty header).
		const callerHeaders = new Headers(init.headers ?? {});
		if (token && !callerHeaders.has('Authorization')) {
			callerHeaders.set('Authorization', `Bearer ${token}`);
		}
		return fetch(`${BACKEND_URL}${path}`, { ...init, headers: callerHeaders });
	};
}
