import type { HandleClientError } from '@sveltejs/kit/hooks';

import {
	PUBLIC_SENTRY_DSN,
	PUBLIC_SENTRY_ENVIRONMENT,
	PUBLIC_SENTRY_TRACES_SAMPLE_RATE
} from '$app/env/public';

import * as Sentry from '@sentry/sveltekit';
import { SENTRY_DATA_COLLECTION } from '#lib/sentry.js';

if (PUBLIC_SENTRY_DSN) {
	Sentry.init({
		dsn: PUBLIC_SENTRY_DSN,
		environment: PUBLIC_SENTRY_ENVIRONMENT ?? 'production',
		tracesSampleRate: Number(PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? '0.1'),
		// Privacy page: nothing about the person in reports.
		dataCollection: SENTRY_DATA_COLLECTION,
		// The SDK's SvelteKit page tracing subscribes to `$app/stores`, which this
		// SvelteKit removed: it throws and breaks every page. Errors only, for now.
		integrations: (defaults) => defaults.filter((i) => i.name !== 'BrowserTracing')
	});
}

export const handleError: HandleClientError = Sentry.handleErrorWithSentry();
