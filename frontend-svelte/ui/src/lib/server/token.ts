/**
 * Read the `role` claim of a JWT *without verifying it*. Only for UI hints
 * (e.g. hiding edit buttons for the read-only demo account): the backend
 * re-verifies the token and enforces the role on every request.
 */
export function tokenRole(token: string): string | null {
	try {
		const payload = token.split('.')[1];
		if (!payload) return null;
		const json = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
		return typeof json?.role === 'string' ? json.role : null;
	} catch {
		return null;
	}
}
