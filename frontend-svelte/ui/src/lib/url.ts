/**
 * `url` when it is an http(s) link, else `''`. Links from the library, IMSLP
 * and the AI agents are data: rendered as-is, a `javascript:` or `data:` URL
 * would run on click.
 */
export function httpUrl(url: unknown): string {
	return typeof url === 'string' && /^https?:\/\//i.test(url.trim()) ? url.trim() : '';
}
