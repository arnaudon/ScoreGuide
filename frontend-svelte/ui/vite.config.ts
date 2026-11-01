/// <reference types="vitest/config" />
import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

import { paraglideVitePlugin } from '@inlang/paraglide-js';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import { playwright } from '@vitest/browser-playwright';
import { sveltekit } from '@sveltejs/kit/vite';

// Default matches the previous hardcoded list so prod CSRF keeps working
// if CSRF_TRUSTED_ORIGINS isn't set. The deploy workflow may override it.
const DEFAULT_TRUSTED_ORIGINS = [
	'localhost',
	'127.0.0.1',
	'188.213.128.236',
	'http://188.213.128.236',
	'https://188.213.128.236'
];

const trustedOrigins = process.env.CSRF_TRUSTED_ORIGINS
	? process.env.CSRF_TRUSTED_ORIGINS.split(',')
			.map((o) => o.trim())
			.filter(Boolean)
	: DEFAULT_TRUSTED_ORIGINS;

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			preprocess: [vitePreprocess()],
			adapter: adapter(),
			csrf: { trustedOrigins }
		}),
		paraglideVitePlugin({ project: './project.inlang', outdir: './src/lib/paraglide' })
	],
	server: {
		allowedHosts: ['scoreguide.ch'],
		watch: {
			usePolling: true
		}
	},
	test: {
		expect: { requireAssertions: true },
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'client',
					browser: {
						enabled: true,
						provider: playwright(),
						instances: [{ browser: 'chromium', headless: true }]
					},
					include: ['src/**/*.svelte.{test,spec}.{js,ts}'],
					exclude: ['src/lib/server/**']
				}
			},

			{
				extends: './vite.config.ts',
				test: {
					name: 'server',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
