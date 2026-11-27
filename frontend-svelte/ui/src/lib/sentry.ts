import type * as Sentry from '@sentry/sveltekit';

type DataCollection = NonNullable<NonNullable<Parameters<typeof Sentry.init>[0]>['dataCollection']>;

/**
 * What error reports may carry (the privacy page promises no IP address, files
 * or typed text): the error, the route and the browser, nothing about the
 * person. Query strings are out too: reset and verification links carry tokens.
 */
export const SENTRY_DATA_COLLECTION: DataCollection = {
	userInfo: false,
	cookies: false,
	httpHeaders: false,
	httpBodies: [],
	urlQueryParams: false,
	genAI: { inputs: false, outputs: false },
	mcp: { inputs: false, outputs: false },
	stackFrameVariables: false
};
