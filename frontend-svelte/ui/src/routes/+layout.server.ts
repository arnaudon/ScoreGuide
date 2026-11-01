import type { LayoutServerLoad } from './$types';
import { apiFetch } from '$lib/server/fetchApi.js';

export const load: LayoutServerLoad = async ({ cookies, fetch, url }) => {
	// Auth state only lives in a cookie, which SvelteKit doesn't track as a load
	// dependency. Reading the pathname makes this load re-run on every client-side
	// navigation, so when a page load clears an expired token and redirects to
	// /login, the layout drops the sidebar instead of keeping stale `loggedIn: true`.
	void url.pathname;
	const token = cookies.get('access_token');
	if (!token) {
		return { loggedIn: false, isAdmin: false };
	}

	const api = apiFetch(fetch, token);
	try {
		const res = await api('/is_admin');
		if (!res.ok) {
			return { loggedIn: false, isAdmin: false };
		}
		const isAdmin = await res.json();
		return { loggedIn: true, isAdmin: Boolean(isAdmin) };
	} catch (e) {
		console.error('Failed to check admin status:', e);
		return { loggedIn: true, isAdmin: false };
	}
};
