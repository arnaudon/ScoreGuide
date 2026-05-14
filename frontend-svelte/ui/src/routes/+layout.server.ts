import type { LayoutServerLoad } from './$types';
import { apiFetch } from '$lib/server/fetchApi.js';

export const load: LayoutServerLoad = async ({ cookies, fetch }) => {
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
