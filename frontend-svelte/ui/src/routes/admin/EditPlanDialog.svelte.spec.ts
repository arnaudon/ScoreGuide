import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import EditPlanDialog from './EditPlanDialog.svelte';
import type { AdminUser } from '#lib/types.js';

function makeUser(overrides: Partial<AdminUser> = {}): AdminUser {
	return {
		id: 42,
		username: 'alice',
		email: 'alice@example.com',
		first_name: null,
		last_name: null,
		instrument: null,
		role: 'user',
		plan: 'pro',
		last_login: null,
		score_count: 0,
		ai_allowance: 1234,
		storage_limit_mb: null,
		...overrides
	};
}

describe('EditPlanDialog.svelte', () => {
	it('renders nothing visible when closed', async () => {
		render(EditPlanDialog, { open: false, user: makeUser() });
		await expect.element(page.getByText(/Save Changes/i)).not.toBeInTheDocument();
	});

	it("shows the user's plan and overrides, empty when using the plan's", async () => {
		render(EditPlanDialog, { open: true, user: makeUser() });
		await expect.element(page.getByText('Plan for alice')).toBeInTheDocument();
		await expect.element(page.getByLabelText('Plan', { exact: true })).toHaveValue('pro');
		await expect.element(page.getByLabelText('AI tokens per month')).toHaveValue(1234);
		await expect.element(page.getByLabelText('Storage (MB)')).toHaveValue(null);
	});
});
