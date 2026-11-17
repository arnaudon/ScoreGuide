import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: 'e2e',
	use: {
		baseURL: 'http://localhost:4173',
		// French is the default locale; the e2e tests assert on English text.
		storageState: {
			cookies: [
				{
					name: 'PARAGLIDE_LOCALE',
					value: 'en',
					domain: 'localhost',
					path: '/',
					expires: -1,
					httpOnly: false,
					secure: false,
					sameSite: 'Lax'
				}
			],
			origins: []
		}
	},
	webServer: [
		{
			command: 'node e2e/stub-backend.mjs',
			port: 9999,
			reuseExistingServer: !process.env.CI
		},
		{
			command: 'npm run build && npm run preview',
			port: 4173,
			reuseExistingServer: !process.env.CI,
			env: {
				BACKEND_URL: 'http://localhost:9999',
				PUBLIC_BACKEND_URL: 'http://localhost:9999',
				// adapter-node needs its public origin to validate CSRF for POSTs.
				ORIGIN: 'http://localhost:4173'
			}
		}
	]
});
