import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { dev } from '$app/environment';
import { apiFetch } from '$lib/server/fetchApi.js';
import { buildScoreUpdatePayload } from '$lib/server/scoreUpdate.js';
import type { Score } from '$lib/types.js';

export const load: PageServerLoad = async ({ cookies, params, fetch }) => {
	const token = cookies.get('access_token');
	if (!token) {
		redirect(303, '/login');
	}

	const api = apiFetch(fetch, token);
	try {
		const response = await api(`/scores/${params.id}`);

		if (response.ok) {
			const score = (await response.json()) as Score;

			cookies.set('last_score_id', params.id, {
				path: '/',
				httpOnly: true,
				secure: !dev,
				sameSite: 'lax',
				maxAge: 60 * 60 * 24 * 30 // 30 days
			});

			return { score };
		}
	} catch (error) {
		console.error('Failed to fetch score:', error);
	}

	return { score: null };
};

export const actions: Actions = {
	update_score: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { error: 'Unauthorized' });
		}

		const data = await request.formData();
		const id = data.get('id');
		if (!id) {
			return fail(400, { error: 'Missing score ID' });
		}

		const payload = buildScoreUpdatePayload(data);

		const api = apiFetch(fetch, token);
		try {
			const res = await api(`/scores/${id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});

			if (!res.ok) {
				return fail(res.status, { error: 'Failed to update score' });
			}

			return { success: true, scoreUpdated: true };
		} catch (error) {
			console.error('Update score error:', error);
			return fail(500, { error: 'Server error when contacting backend' });
		}
	}
};
