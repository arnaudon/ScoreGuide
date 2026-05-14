import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { dev } from '$app/environment';
import { apiFetch } from '$lib/server/fetchApi.js';
import type { Score } from '$lib/types.js';

export const load: PageServerLoad = async ({ cookies, params, fetch }) => {
	const token = cookies.get('access_token');
	if (!token) {
		redirect(303, '/login');
	}

	const api = apiFetch(fetch, token);
	try {
		const response = await api('/scores');

		if (response.ok) {
			const scores = (await response.json()) as Score[];
			const score = scores.find((s) => s.id === Number(params.id));

			if (score) {
				cookies.set('last_score_id', params.id, {
					path: '/',
					httpOnly: true,
					secure: !dev,
					sameSite: 'lax',
					maxAge: 60 * 60 * 24 * 30 // 30 days
				});
			}

			return { score };
		}
	} catch (error) {
		console.error('Failed to fetch score:', error);
	}

	return { score: null };
};
