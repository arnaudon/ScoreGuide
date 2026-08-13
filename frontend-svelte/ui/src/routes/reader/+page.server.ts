import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ cookies }) => {
	const token = cookies.get('access_token');
	if (!token) {
		redirect(303, '/login');
	}

	const lastScoreId = cookies.get('last_score_id');

	// Only numeric ids — the cookie is client-controlled, so don't let it
	// inject path segments into the redirect target.
	if (lastScoreId && /^\d+$/.test(lastScoreId)) {
		redirect(303, `/reader/${lastScoreId}`);
	}

	return {};
};
