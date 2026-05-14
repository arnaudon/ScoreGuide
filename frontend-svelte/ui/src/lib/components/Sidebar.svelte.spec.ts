import { page } from 'vitest/browser';
import { describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import SidebarHarness from './SidebarHarness.test.svelte';

// `Sidebar.svelte` reads `$app/state.page.data.isAdmin` to gate the admin
// nav item. Default to non-admin; one test re-mocks to admin.
vi.mock('$app/state', () => ({
	page: { data: { isAdmin: false }, url: new URL('http://localhost/') }
}));

describe('Sidebar.svelte', () => {
	it('renders the brand', async () => {
		render(SidebarHarness);
		await expect.element(page.getByRole('heading', { name: /scoreguide/i })).toBeInTheDocument();
	});

	it('shows the four always-on nav links', async () => {
		render(SidebarHarness);
		await expect.element(page.getByRole('link', { name: /home/i })).toBeInTheDocument();
		await expect.element(page.getByRole('link', { name: /database/i })).toBeInTheDocument();
		await expect.element(page.getByRole('link', { name: /pdf/i })).toBeInTheDocument();
		await expect.element(page.getByRole('link', { name: /account/i })).toBeInTheDocument();
	});

	it('hides the admin nav link when isAdmin is false', async () => {
		render(SidebarHarness);
		await expect.element(page.getByRole('link', { name: /admin/i })).not.toBeInTheDocument();
	});

	it('exposes the language toggle group with EN + FR buttons', async () => {
		render(SidebarHarness);
		await expect.element(page.getByRole('group', { name: /language/i })).toBeInTheDocument();
		await expect
			.element(page.getByRole('button', { name: /switch to english/i }))
			.toBeInTheDocument();
		await expect
			.element(page.getByRole('button', { name: /switch to french/i }))
			.toBeInTheDocument();
	});

	it('exposes the logout submit button', async () => {
		render(SidebarHarness);
		await expect.element(page.getByRole('button', { name: /logout/i })).toBeInTheDocument();
	});
});
