import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { dev } from '$app/environment';
import { apiFetch } from '$lib/server/fetchApi.js';
import { buildScoreUpdatePayload } from '$lib/server/scoreUpdate.js';
import type { Score, SectionsResponse } from '$lib/types.js';

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

			return { score, toc: await loadSections(api, params.id) };
		}
	} catch (error) {
		console.error('Failed to fetch score:', error);
	}

	return { score: null, toc: EMPTY_TOC };
};

const EMPTY_TOC: SectionsResponse = { status: 'none', sections: [] };

/** The table of contents is optional: never fail the page over it. */
async function loadSections(
	api: ReturnType<typeof apiFetch>,
	id: string
): Promise<SectionsResponse> {
	try {
		const res = await api(`/scores/${id}/sections`);
		if (res.ok) return (await res.json()) as SectionsResponse;
	} catch (error) {
		console.error('Failed to fetch sections:', error);
	}
	return EMPTY_TOC;
}

export const actions: Actions = {
	generate_toc: async ({ cookies, params, fetch }) => {
		const token = cookies.get('access_token');
		if (!token) {
			return fail(401, { error: 'Unauthorized' });
		}
		try {
			const res = await apiFetch(fetch, token)(`/scores/${params.id}/sections/generate`, {
				method: 'POST'
			});
			if (!res.ok) {
				return fail(res.status, { tocError: true });
			}
			return { tocStarted: true };
		} catch (error) {
			console.error('Generate TOC error:', error);
			return fail(500, { tocError: true });
		}
	},
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
