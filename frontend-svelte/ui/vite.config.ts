/// <reference types="vitest/config" />
import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

import { paraglideVitePlugin } from '@inlang/paraglide-js';
import tailwindcss from '@tailwindcss/vite';
import { cpSync } from 'node:fs';
import { defineConfig, type Plugin } from 'vite';
import { playwright } from '@vitest/browser-playwright';
import { sveltekit } from '@sveltejs/kit/vite';

// Form POSTs must come from the app's own origin (ORIGIN in prod compose).
// CSRF_TRUSTED_ORIGINS (build time, comma-separated full origins such as
// `https://example.com`) adds others; none by default.
const trustedOrigins = (process.env.CSRF_TRUSTED_ORIGINS ?? '')
	.split(',')
	.map((o) => o.trim())
	.filter(Boolean);

/**
 * Content-Security-Policy, set by SvelteKit so its own inline scripts get a
 * nonce. Everything is same-origin except Sentry's ingest endpoint. Inline
 * styles stay allowed (Svelte transitions and shadcn components set them);
 * pdf.js needs WebAssembly for its image decoders and runs in a module worker.
 */
const csp = {
	mode: 'auto' as const,
	directives: {
		'default-src': ['self' as const],
		'script-src': ['self' as const, 'wasm-unsafe-eval' as const],
		'style-src': ['self' as const, 'unsafe-inline' as const],
		'img-src': ['self' as const, 'data:' as const, 'blob:' as const],
		'font-src': ['self' as const, 'data:' as const],
		'connect-src': ['self' as const, 'https://*.sentry.io' as const],
		'worker-src': ['self' as const, 'blob:' as const],
		// YouTube's privacy-enhanced player, loaded only when the user clicks Play.
		'frame-src': ['self' as const, 'blob:' as const, 'https://www.youtube-nocookie.com' as const],
		'object-src': ['none' as const],
		'base-uri': ['self' as const],
		'form-action': ['self' as const],
		'frame-ancestors': ['self' as const]
	}
};

/**
 * pdf.js loads fonts, character maps, colour profiles and image decoders
 * (JBIG2/JPEG 2000 — common in scanned IMSLP scores) at runtime by URL.
 * Copy them from the installed pdfjs-dist into static/pdfjs/ (gitignored)
 * so they always match the library version.
 */
function pdfjsAssets(): Plugin {
	return {
		name: 'pdfjs-assets',
		buildStart() {
			for (const dir of ['cmaps', 'standard_fonts', 'wasm', 'iccs']) {
				cpSync(
					new URL(`./node_modules/pdfjs-dist/${dir}`, import.meta.url),
					new URL(`./static/pdfjs/${dir}`, import.meta.url),
					{ recursive: true }
				);
			}
		}
	};
}

export default defineConfig({
	plugins: [
		pdfjsAssets(),
		tailwindcss(),
		sveltekit({
			preprocess: [vitePreprocess()],
			adapter: adapter(),
			csrf: { trustedOrigins },
			csp
		}),
		paraglideVitePlugin({
			project: './project.inlang',
			outdir: './src/lib/paraglide',
			// One module per locale instead of one per message (the plugin's
			// default): far fewer modules for Vite/Rollup to hold during the
			// production build, which runs on the same small VPS as prod.
			// Same choice as GardenAI (#619 there).
			outputStructure: 'locale-modules'
		})
	],
	optimizeDeps: {
		// Loaded lazily by ScoreViewer: pre-bundle it so Vite doesn't
		// discover it mid-run and reload (breaks in-flight browser tests).
		include: ['pdfjs-dist/legacy/build/pdf.mjs']
	},
	server: {
		allowedHosts: ['scoreguide.ch'],
		watch: {
			usePolling: true
		}
	},
	test: {
		expect: { requireAssertions: true },
		// The app defaults to French; tests assert on the English strings.
		setupFiles: ['./src/test-setup.ts'],
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
