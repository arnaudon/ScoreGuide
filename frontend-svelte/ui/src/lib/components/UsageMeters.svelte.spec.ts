import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import UsageMeters from './UsageMeters.svelte';
import type { UsageSummary } from '#lib/types.js';

const MB = 1024 * 1024;
const usage = (overrides: Partial<UsageSummary> = {}): UsageSummary => ({
	plan: 'free',
	ai_used: 190,
	ai_allowance: 200,
	ai_resets_at: '2026-12-01T00:00:00',
	storage_used: 120 * MB,
	storage_limit: 500 * MB,
	...overrides
});

describe('UsageMeters.svelte', () => {
	it('shows the plan, both meters and the upgrade hint on Free', async () => {
		render(UsageMeters, { usage: usage() });
		await expect.element(page.getByText('Free', { exact: true })).toBeInTheDocument();
		await expect.element(page.getByText('95% used · renews on December 1')).toBeInTheDocument();
		await expect.element(page.getByText('120 MB of 500 MB')).toBeInTheDocument();
		await expect
			.element(page.getByRole('meter', { name: 'AI assistant this month' }))
			.toHaveAttribute('aria-valuenow', '95');
		await expect.element(page.getByText(/Contact us to move to Pro/)).toBeInTheDocument();
	});

	it('hides the upgrade hint on Pro', async () => {
		render(UsageMeters, { usage: usage({ plan: 'pro', ai_used: 0 }) });
		await expect.element(page.getByText('Pro', { exact: true })).toBeInTheDocument();
		await expect.element(page.getByText(/move to Pro/)).not.toBeInTheDocument();
	});
});
