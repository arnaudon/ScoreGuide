import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

const BACKEND_URL = 'http://localhost:8000';

export const load: PageServerLoad = async ({ cookies, fetch }) => {
	const token = cookies.get('access_token');
	
	if (!token) {
		redirect(303, '/login');
	}

	try {
		const response = await fetch(`${BACKEND_URL}/scores`, {
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		if (response.ok) {
			const scores = await response.json();
			return { scores };
		}
	} catch (error) {
		console.error('Failed to fetch scores:', error);
	}

	return { scores: [] };
};
