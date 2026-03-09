import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';

const BACKEND_URL = 'http://localhost:8000';

export const load: PageServerLoad = async ({ cookies }) => {
	const token = cookies.get('access_token');
	if (!token) {
		redirect(303, '/login');
	}
	return {};
};

export const actions: Actions = {
	ask: async ({ request, cookies, fetch }) => {
		const token = cookies.get('access_token');
		const data = await request.formData();
		const question = data.get('question');

		if (!question) {
			return fail(400, { error: 'Missing question' });
		}

		try {
			const response = await fetch(`${BACKEND_URL}/agent?prompt=${encodeURIComponent(question.toString())}`, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${token}`
				}
			});

			if (response.ok) {
				const result = await response.json();
				return { success: true, answer: result, question: question.toString() };
			} else {
				return fail(response.status, { error: `Failed to get response (${response.status})` });
			}
		} catch (error) {
			console.error('Agent error:', error);
			return fail(500, { error: 'Server error when contacting backend' });
		}
	}
};
