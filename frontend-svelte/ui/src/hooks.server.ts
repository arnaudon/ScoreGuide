import { sequence } from '@sveltejs/kit/hooks';
import { env } from '$env/dynamic/private';
import type { Handle, HandleServerError } from '@sveltejs/kit';
import * as Sentry from '@sentry/sveltekit';
import { getTextDirection } from '$lib/paraglide/runtime';
import { paraglideMiddleware } from '$lib/paraglide/server';

// Opt-in: if SENTRY_DSN isn't set, init is skipped and Sentry.sentryHandle
// still short-circuits cleanly.
if (env.SENTRY_DSN) {
	Sentry.init({
		dsn: env.SENTRY_DSN,
		environment: env.SENTRY_ENVIRONMENT ?? 'production',
		tracesSampleRate: Number(env.SENTRY_TRACES_SAMPLE_RATE ?? '0.1')
	});
}

const handleParaglide: Handle = ({ event, resolve }) =>
	paraglideMiddleware(event.request, ({ request, locale }) => {
		event.request = request;

		return resolve(event, {
			transformPageChunk: ({ html }) =>
				html
					.replace('%paraglide.lang%', locale)
					.replace('%paraglide.dir%', getTextDirection(locale))
		});
	});

export const handle: Handle = sequence(Sentry.sentryHandle(), handleParaglide);

const sentryError = Sentry.handleErrorWithSentry();
export const handleError: HandleServerError = (input) => {
	// 404s (and other 4xx) come almost entirely from scanner probes
	// hitting /sitemaps.xml, /wp-admin, /.git/config, etc. Don't log or
	// report them — SvelteKit already returns the right status code.
	if (typeof input.status === 'number' && input.status >= 400 && input.status < 500) {
		return;
	}
	return sentryError(input);
};
