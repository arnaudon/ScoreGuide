import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ cookies }) => {
	const token = cookies.get('access_token');
	let isAdmin = false;

	if (token) {
		try {
			const payloadBase64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
			const payload = JSON.parse(atob(payloadBase64));
			isAdmin = payload.role === 'admin' || payload.is_admin === true;
		} catch (e) {
			console.error('Failed to parse token payload:', e);
		}
	}
	
	return {
		loggedIn: !!token,
		isAdmin
	};
};
