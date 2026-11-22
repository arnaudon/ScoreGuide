import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from './$types';
import { dev } from '$app/env';
import { apiFetch } from '#lib/server/fetchApi.js';
import * as m from '#lib/paraglide/messages.js';
import { detailMessage } from '#lib/apiError.js';
import { passwordLengthOk } from '#lib/password.js';

export const actions: Actions = {
	login: async ({ request, cookies, fetch }) => {
		const data = await request.formData();
		const username = data.get('username');
		const password = data.get('password');
		const remember = data.get('remember');

		if (!username || !password) {
			return fail(400, { username: username?.toString(), error: m.err_missing_credentials() });
		}

		const body = new URLSearchParams();
		body.append('username', username.toString());
		body.append('password', password.toString());
		const rememberMe = remember === 'on';
		if (rememberMe) body.append('remember', 'true');

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
				error: result.detail || m.err_login_failed()
			});
		}

		const tokenData = await response.json();

		// Must match the JWT lifetime issued by the backend (users.py REMEMBER_ME_EXPIRE_MINUTES).
		const maxAge = rememberMe ? 60 * 60 * 24 * 30 : 60 * 60 * 24; // 30 days or 1 day

		cookies.set('access_token', tokenData.access_token, {
			path: '/',
			httpOnly: true,
			secure: !dev,
			sameSite: 'lax',
			maxAge
		});

		redirect(303, '/home');
	},

	demo: async ({ cookies, fetch }) => {
		const api = apiFetch(fetch, undefined);
		const response = await api('/demo-login', { method: 'POST' });
		if (!response.ok) {
			return fail(response.status, { error: m.err_demo_unavailable() });
		}
		const tokenData = await response.json();
		cookies.set('access_token', tokenData.access_token, {
			path: '/',
			httpOnly: true,
			secure: !dev,
			sameSite: 'lax',
			maxAge: 60 * 60 * 24 // must match the backend's 1-day demo token
		});
		redirect(303, '/db-viewer');
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
				error: m.err_missing_register_fields()
			});
		}

		if (!passwordLengthOk(password.toString())) {
			return fail(400, {
				username: username.toString(),
				email: email.toString(),
				instrument: instrument?.toString(),
				error: m.err_password_length()
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
			let errorMsg: string = m.err_registration_failed();
			try {
				const result = await response.json();
				errorMsg = detailMessage(result.detail, errorMsg);
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
				message: m.registration_success_login()
			};
		}
	}
};
