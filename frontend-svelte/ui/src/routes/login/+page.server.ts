import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from './$types';
import { dev } from '$app/env';
import { apiFetch } from '#lib/server/fetchApi.js';
import * as m from '#lib/paraglide/messages.js';
import { detailMessage } from '#lib/apiError.js';
import { passwordLengthOk } from '#lib/password.js';
import { callBackend } from '#lib/server/callBackend.js';

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
		const answer = await callBackend(() =>
			api('/token', {
				method: 'POST',
				headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
				body
			})
		);
		if (!answer || (answer.res.ok && typeof answer.data.access_token !== 'string')) {
			return fail(503, { username: username.toString(), error: m.err_service_unavailable() });
		}
		if (!answer.res.ok) {
			return fail(answer.res.status, {
				username: username.toString(),
				error: detailMessage(answer.data.detail, m.err_login_failed())
			});
		}
		const accessToken = answer.data.access_token as string;

		// Must match the JWT lifetime issued by the backend (users.py REMEMBER_ME_EXPIRE_MINUTES).
		const maxAge = rememberMe ? 60 * 60 * 24 * 30 : 60 * 60 * 24; // 30 days or 1 day

		cookies.set('access_token', accessToken, {
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
		const answer = await callBackend(() => api('/demo-login', { method: 'POST' }));
		if (!answer) return fail(503, { error: m.err_service_unavailable() });
		if (!answer.res.ok || typeof answer.data.access_token !== 'string') {
			return fail(answer.res.ok ? 503 : answer.res.status, { error: m.err_demo_unavailable() });
		}
		cookies.set('access_token', answer.data.access_token, {
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
		const musicProfile = data.get('music_profile')?.toString() ?? '';

		if (!username || !password || !email) {
			return fail(400, {
				username: username?.toString(),
				email: email?.toString(),
				instrument: instrument?.toString(),
				musicProfile,
				error: m.err_missing_register_fields()
			});
		}

		if (!passwordLengthOk(password.toString())) {
			return fail(400, {
				username: username.toString(),
				email: email.toString(),
				instrument: instrument?.toString(),
				musicProfile,
				error: m.err_password_length()
			});
		}

		const api = apiFetch(fetch, undefined);
		const answer = await callBackend(() =>
			api('/users', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					username: username.toString(),
					password: password.toString(),
					email: email.toString(),
					instrument: instrument?.toString(),
					music_profile: musicProfile.trim() || undefined
				})
			})
		);

		if (!answer || !answer.res.ok) {
			return fail(answer ? answer.res.status : 503, {
				username: username.toString(),
				email: email.toString(),
				instrument: instrument?.toString(),
				musicProfile,
				error: answer
					? detailMessage(answer.data.detail, m.err_registration_failed())
					: m.err_service_unavailable()
			});
		}

		// Automatically log in the user after successful registration
		const body = new URLSearchParams();
		body.append('username', username.toString());
		body.append('password', password.toString());

		// The account exists now: if this login fails, say so and let the user sign in.
		const login = await callBackend(() =>
			api('/token', {
				method: 'POST',
				headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
				body
			})
		);

		if (login?.res.ok && typeof login.data.access_token === 'string') {
			cookies.set('access_token', login.data.access_token, {
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
