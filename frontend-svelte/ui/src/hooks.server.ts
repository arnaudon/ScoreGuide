import {
	sequence,
	type Handle,
	type HandleFetch,
	type HandleServerError
} from '@sveltejs/kit/hooks';
import { BACKEND_URL } from '#lib/server/api.js';
import { SENTRY_DSN, SENTRY_ENVIRONMENT, SENTRY_TRACES_SAMPLE_RATE } from '$app/env/private';
import * as Sentry from '@sentry/sveltekit';
import { getTextDirection } from '#lib/paraglide/runtime.js';
import { paraglideMiddleware } from '#lib/paraglide/server.js';
import { createInitialModeExpression } from 'mode-watcher';

// Opt-in: if SENTRY_DSN isn't set, init is skipped and Sentry.sentryHandle
// still short-circuits cleanly.
if (SENTRY_DSN) {
	Sentry.init({
		dsn: SENTRY_DSN,
		environment: SENTRY_ENVIRONMENT ?? 'production',
		tracesSampleRate: Number(SENTRY_TRACES_SAMPLE_RATE ?? '0.1')
	});
}

const MODE_INIT = createInitialModeExpression();

// The Paraglide strategy has no `url` entry, so the middleware never rewrites the
// request (and Kit 3 makes `event.request` read-only); it only sets the locale.
const handleParaglide: Handle = ({ event, resolve }) =>
	paraglideMiddleware(event.request, ({ locale }) => {
		return resolve(event, {
			transformPageChunk: ({ html }) =>
				html
					.replace('%paraglide.lang%', locale)
					.replace('%paraglide.dir%', getTextDirection(locale))
					// mode-watcher's own copy of this script would be inline without
					// the CSP nonce; app.html's <script nonce> carries it instead.
					.replace('%modewatcher.init%', () => MODE_INIT)
		});
	});

export const handle: Handle = sequence(Sentry.sentryHandle(), handleParaglide);

/**
 * Tell the backend who the visitor is. Every backend call comes from this
 * server, so without it the backend's per-IP rate limits (login, sign-up,
 * password reset) would be one bucket shared by every visitor — and anyone
 * could exhaust it for everyone. Behind Caddy, `getClientAddress` reads the
 * X-Forwarded-For entry Caddy sets (ADDRESS_HEADER / XFF_DEPTH in compose).
 * Any value the browser sent is overwritten.
 */
export const handleFetch: HandleFetch = ({ event, request, fetch }) => {
	if (request.url.startsWith(BACKEND_URL)) {
		let address: string | undefined;
		try {
			address = event.getClientAddress();
		} catch {
			address = undefined;
		}
		const headers = new Headers(request.headers);
		headers.delete('X-Client-IP');
		if (address) headers.set('X-Client-IP', address);
		request = new Request(request, { headers });
	}
	return fetch(request);
};

// Kit 3 passes every error here with a `kind`. Sentry only reports `unknown`
// ones (bugs); app errors, validation errors and framework errors such as the 404s
// from scanner probes (/wp-admin, /.git/config, ...) are skipped.
export const handleError: HandleServerError = Sentry.handleErrorWithSentry();
