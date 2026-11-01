import { sequence, type Handle, type HandleServerError } from '@sveltejs/kit/hooks';
import { SENTRY_DSN, SENTRY_ENVIRONMENT, SENTRY_TRACES_SAMPLE_RATE } from '$app/env/private';
import * as Sentry from '@sentry/sveltekit';
import { getTextDirection } from '#lib/paraglide/runtime.js';
import { paraglideMiddleware } from '#lib/paraglide/server.js';

// Opt-in: if SENTRY_DSN isn't set, init is skipped and Sentry.sentryHandle
// still short-circuits cleanly.
if (SENTRY_DSN) {
	Sentry.init({
		dsn: SENTRY_DSN,
		environment: SENTRY_ENVIRONMENT ?? 'production',
		tracesSampleRate: Number(SENTRY_TRACES_SAMPLE_RATE ?? '0.1')
	});
}

// The Paraglide strategy has no `url` entry, so the middleware never rewrites the
// request (and Kit 3 makes `event.request` read-only); it only sets the locale.
const handleParaglide: Handle = ({ event, resolve }) =>
	paraglideMiddleware(event.request, ({ locale }) => {
		return resolve(event, {
			transformPageChunk: ({ html }) =>
				html
					.replace('%paraglide.lang%', locale)
					.replace('%paraglide.dir%', getTextDirection(locale))
		});
	});

export const handle: Handle = sequence(Sentry.sentryHandle(), handleParaglide);

// Kit 3 passes every error here with a `kind`. Sentry only reports `unknown`
// ones (bugs); app errors, validation errors and framework errors such as the 404s
// from scanner probes (/wp-admin, /.git/config, ...) are skipped.
export const handleError: HandleServerError = Sentry.handleErrorWithSentry();
