import { redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { dev } from '$app/env';

/**
 * GET never signs out: a link or an `<img src="/logout">` on another site
 * could otherwise log visitors out. Signed-in visitors get a button that
 * POSTs the form below (the sidebar and the demo banner post it directly).
 */
export const load: PageServerLoad = async ({ cookies }) => {
	if (!cookies.get('access_token')) redirect(303, '/login');
	return {};
};

export const actions: Actions = {
	default: async ({ cookies, request }) => {
		cookies.delete('access_token', { path: '/', httpOnly: true, secure: !dev, sameSite: 'lax' });
		// The demo banner's "create an account" lands on the sign-up form.
		const form = await request.formData().catch(() => null);
		redirect(303, form?.get('next') === 'signup' ? '/login?signup' : '/login');
	}
};
