import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: 'e2e',
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
				PUBLIC_BACKEND_URL: 'http://localhost:9999'
			}
		}
	]
});
