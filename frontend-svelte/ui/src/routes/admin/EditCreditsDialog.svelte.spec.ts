import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import EditCreditsDialog from './EditCreditsDialog.svelte';
import type { AdminUser } from '$lib/types.js';

function makeUser(overrides: Partial<AdminUser> = {}): AdminUser {
	return {
		id: 42,
		username: 'alice',
		email: 'alice@example.com',
		first_name: null,
		last_name: null,
		instrument: null,
		role: 'user',
		credits: 3,
		max_credits: 20,
		last_login: null,
		score_count: 0,
		...overrides
	};
}

describe('EditCreditsDialog.svelte', () => {
	it('renders nothing visible when open is false', async () => {
		render(EditCreditsDialog, { open: false, user: makeUser() });
		await expect.element(page.getByText(/Save Changes/i)).not.toBeInTheDocument();
	});

	it('shows the user-named title and prefilled max_credits when open', async () => {
		render(EditCreditsDialog, { open: true, user: makeUser({ max_credits: 50 }) });
		await expect.element(page.getByText(/alice/i)).toBeInTheDocument();
		// The only number input in the dialog. Avoids matching the dialog
		// title which also contains the string "Max Credits".
		await expect.element(page.getByRole('spinbutton')).toHaveValue(50);
	});

	it('exposes both set_credits and refill_credits forms', async () => {
		render(EditCreditsDialog, { open: true, user: makeUser() });
		await expect.element(page.getByRole('button', { name: /save changes/i })).toBeInTheDocument();
		await expect.element(page.getByRole('button', { name: /refill credits/i })).toBeInTheDocument();
	});

	it('disables refill when credits === max_credits', async () => {
		render(EditCreditsDialog, { open: true, user: makeUser({ credits: 20, max_credits: 20 }) });
		await expect.element(page.getByRole('button', { name: /refill credits/i })).toBeDisabled();
	});

	it('renders falls back to empty username placeholder when user is null', async () => {
		render(EditCreditsDialog, { open: true, user: null });
		// With no user, the body forms are hidden but the title still renders.
		await expect.element(page.getByText(/edit max credits/i)).toBeInTheDocument();
		await expect
			.element(page.getByRole('button', { name: /save changes/i }))
			.not.toBeInTheDocument();
	});
});
