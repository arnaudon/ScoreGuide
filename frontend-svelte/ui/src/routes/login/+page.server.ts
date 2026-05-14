import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from './$types';
import { dev } from '$app/environment';
import { apiFetch } from '$lib/server/fetchApi.js';

export const actions: Actions = {
	login: async ({ request, cookies, fetch }) => {
		const data = await request.formData();
		const username = data.get('username');
		const password = data.get('password');
		const remember = data.get('remember');

		if (!username || !password) {
			return fail(400, { username: username?.toString(), error: 'Missing username or password' });
		}

		const body = new URLSearchParams();
		body.append('username', username.toString());
		body.append('password', password.toString());

		const api = apiFetch(fetch, undefined);
		const response = await api('/token', {
			method: 'POST',
			headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
			body
		});

		if (!response.ok) {
			const result = await response.json();
			return fail(response.status, {
				username: username.toString(),
				error: result.detail || 'Login failed'
			});
		}

		const tokenData = await response.json();

		const maxAge = remember === 'on' ? 60 * 60 * 24 * 30 : 60 * 60 * 24; // 30 days or 1 day

		cookies.set('access_token', tokenData.access_token, {
			path: '/',
			httpOnly: true,
			secure: !dev,
			sameSite: 'lax',
			maxAge
		});

		redirect(303, '/home');
	},

	register: async ({ request, cookies, fetch }) => {
		const data = await request.formData();
		const username = data.get('username');
		const password = data.get('password');
		const email = data.get('email');
		const instrument = data.get('instrument');

		if (!username || !password || !email) {
			return fail(400, {
				username: username?.toString(),
				email: email?.toString(),
				instrument: instrument?.toString(),
				error: 'Missing username, password or email'
			});
		}

		const api = apiFetch(fetch, undefined);
		const response = await api('/users', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				username: username.toString(),
				password: password.toString(),
				email: email.toString(),
				instrument: instrument?.toString()
			})
		});

		if (!response.ok) {
			let errorMsg = 'Registration failed';
			try {
				const result = await response.json();
				errorMsg = result.detail || errorMsg;
			} catch (e) {
				console.error('Failed to parse register error response', e);
			}
			return fail(response.status, {
				username: username.toString(),
				email: email.toString(),
				instrument: instrument?.toString(),
				error: errorMsg
			});
		}

		// Automatically log in the user after successful registration
		const body = new URLSearchParams();
		body.append('username', username.toString());
		body.append('password', password.toString());

		const loginRes = await api('/token', {
			method: 'POST',
			headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
			body
		});

		if (loginRes.ok) {
			const tokenData = await loginRes.json();
			cookies.set('access_token', tokenData.access_token, {
				path: '/',
				httpOnly: true,
				secure: !dev,
				sameSite: 'lax',
				maxAge: 60 * 60 * 24 // 1 day
			});
			redirect(303, '/home');
		} else {
			return {
				username: username.toString(),
				success: true,
				message: 'Registration successful! Please log in.'
			};
		}
	}
};
