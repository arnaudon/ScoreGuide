import { expect, test } from '@playwright/test';

test.describe('login page', () => {
	test('renders the login form with username + password inputs', async ({ page }) => {
		await page.goto('/login');
		await expect(page.getByRole('heading', { name: 'ScoreGuide' })).toBeVisible();
		await expect(page.locator('input[name="username"]')).toBeVisible();
		await expect(page.locator('input[name="password"]')).toBeVisible();
	});

	test('rejects an empty submit and surfaces an error', async ({ page }) => {
		await page.goto('/login');
		await page.getByRole('button', { name: /^login$/i }).click();
		// Wording is i18n-able; assert via the alert landmark instead.
		await expect(page.getByRole('alert')).toBeVisible();
	});
});
