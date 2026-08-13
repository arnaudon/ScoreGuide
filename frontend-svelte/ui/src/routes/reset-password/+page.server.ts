import { fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { apiFetch } from '$lib/server/fetchApi.js';

export const load: PageServerLoad = async ({ url }) => {
	return { token: url.searchParams.get('token') ?? '' };
};

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const data = await request.formData();
		const token = data.get('token');
		const newPassword = data.get('new_password');
		const confirmPassword = data.get('confirm_password');

		if (!token) {
			return fail(400, { token: '', error: 'Missing or invalid reset link' });
		}

		if (!newPassword || !confirmPassword) {
			return fail(400, { token: token.toString(), error: 'Missing password' });
		}

		if (newPassword.toString() !== confirmPassword.toString()) {
			return fail(400, { token: token.toString(), error: 'Passwords do not match' });
		}

		const api = apiFetch(fetch, undefined);
		const response = await api('/reset-password', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ token: token.toString(), new_password: newPassword.toString() })
		});

		if (!response.ok) {
			let errorMsg = 'Something went wrong. Please try again.';
			try {
				const result = await response.json();
				errorMsg = result.detail || errorMsg;
			} catch (e) {
				console.error('Failed to parse reset-password error response', e);
			}
			return fail(response.status, { token: token.toString(), error: errorMsg });
		}

		const result = await response.json();
		return { success: true, message: result.message };
	}
};
