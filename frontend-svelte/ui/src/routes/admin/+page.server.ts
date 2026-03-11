import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { env } from '$env/dynamic/private';

const BACKEND_URL = env.BACKEND_URL || 'http://localhost:8000';

export const load: PageServerLoad = async ({ cookies, fetch }) => {
	const token = cookies.get('access_token');
	
	if (!token) {
		redirect(303, '/login');
	}

	try {
		const payloadBase64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
		const payload = JSON.parse(atob(payloadBase64));
		if (payload.role !== 'admin' && payload.is_admin !== true) {
			redirect(303, '/');
		}

		const response = await fetch(`${BACKEND_URL}/users`, {
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		if (response.ok) {
			const users = await response.json();
			return { users };
		}
	} catch (error) {
		console.error('Failed to fetch users:', error);
	}

	return { users: [] };
};
