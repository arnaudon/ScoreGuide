import { expect, test, type Page } from '@playwright/test';

async function login(page: Page) {
	await page.goto('/login');
	await page.locator('input[name="username"]').fill('test');
	await page.locator('input[name="password"]').fill('hunter2');
	await page.getByRole('button', { name: /^login$/i }).click();
	await expect(page).toHaveURL('/home');
}

test('the home assistant can be switched off for a free library search', async ({ page }) => {
	await login(page);
	const ai = page.getByRole('switch', { name: /AI assistant/ });
	await expect(ai).toHaveAttribute('aria-checked', 'true');
	await expect(page.getByPlaceholder(/Find me piano sonatas/)).toBeVisible();

	// Retried: a click before hydration does nothing.
	await expect(async () => {
		if ((await ai.getAttribute('aria-checked')) === 'true') await ai.click();
		await expect(ai).toHaveAttribute('aria-checked', 'false', { timeout: 1000 });
	}).toPass();
	const search = page.getByRole('searchbox', { name: /search your library/i });
	await search.fill('etude 07');
	await expect(page.getByRole('button', { name: /Etude No\. 07/ })).toBeVisible();
	await search.fill('nothing like this');
	await expect(page.getByText('No score matches.')).toBeVisible();

	// Remembered on this device.
	await page.reload();
	await expect(page.getByRole('switch', { name: /AI assistant/ })).toHaveAttribute(
		'aria-checked',
		'false'
	);
	await page.getByRole('switch', { name: /AI assistant/ }).click();
	await expect(page.getByRole('searchbox', { name: /search your library/i })).toHaveCount(0);
});
