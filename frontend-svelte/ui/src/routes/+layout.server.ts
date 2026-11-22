import type { LayoutServerLoad } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';
import { tokenRole } from '#lib/server/token.js';
import type { User } from '#lib/types.js';

const LOGGED_OUT = { loggedIn: false, isAdmin: false, isDemo: false, emailUnverified: false };

export const load: LayoutServerLoad = async ({ cookies, fetch, url }) => {
	// Auth state only lives in a cookie, which SvelteKit doesn't track as a load
	// dependency. Reading the pathname makes this load re-run on every client-side
	// navigation, so when a page load clears an expired token and redirects to
	// /login, the layout drops the sidebar instead of keeping stale `loggedIn: true`.
	void url.pathname;
	const token = cookies.get('access_token');
	if (!token) {
		return LOGGED_OUT;
	}

	// UI hint only (hide edit controls); the backend enforces read-only.
	const isDemo = tokenRole(token) === 'demo';
	const api = apiFetch(fetch, token);
	try {
		const res = await api('/user');
		if (!res.ok) {
			return LOGGED_OUT;
		}
		const user: User = await res.json();
		return {
			loggedIn: true,
			isAdmin: user.role === 'admin',
			isDemo,
			// Shows the "confirm your email" banner (AI and uploads wait for it).
			emailUnverified: user.email_verified === false
		};
	} catch (e) {
		console.error('Failed to load the current user:', e);
		return { loggedIn: true, isAdmin: false, isDemo, emailUnverified: false };
	}
};
