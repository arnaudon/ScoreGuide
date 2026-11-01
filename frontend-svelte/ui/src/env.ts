import { defineEnvVars } from '@sveltejs/kit/env';

// All optional: unset (or empty) resolves to `undefined`, so callers' `??` / `||`
// defaults apply, matching the old `$env/dynamic/*` behaviour.
const optional = (input: string | undefined) => input || undefined;

export const variables = defineEnvVars({
	PUBLIC_SENTRY_DSN: { public: true, schema: optional },
	PUBLIC_SENTRY_ENVIRONMENT: { public: true, schema: optional },
	PUBLIC_SENTRY_TRACES_SAMPLE_RATE: { public: true, schema: optional },
	SENTRY_DSN: { schema: optional },
	SENTRY_ENVIRONMENT: { schema: optional },
	SENTRY_TRACES_SAMPLE_RATE: { schema: optional },
	BACKEND_URL: { schema: optional }
});
