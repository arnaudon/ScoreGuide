import { fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { apiFetch } from '#lib/server/fetchApi.js';

/** Opens the link from the confirmation email: no login needed. */
export const load: PageServerLoad = async ({ url, fetch, cookies }) => {
	const token = url.searchParams.get('token');
	const loggedIn = Boolean(cookies.get('access_token'));
	if (!token) return { verified: false, loggedIn };
	try {
		const res = await apiFetch(fetch, undefined)('/verify-email', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ token })
		});
		return { verified: res.ok, loggedIn };
	} catch (e) {
		console.error('Email verification failed:', e);
		return { verified: false, loggedIn };
	}
};

export const actions: Actions = {
	/** "Resend the email", from the banner shown on every page. */
	resend: async ({ cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) return fail(401, { resent: false });
		const res = await apiFetch(fetch, token)('/resend-verification', { method: 'POST' });
		if (!res.ok) return fail(res.status, { resent: false });
		return { resent: true };
	}
};
