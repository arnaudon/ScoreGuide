import { expect, test } from '@playwright/test';

async function login(page: import('@playwright/test').Page) {
	await page.goto('/login');
	await page.locator('input[name="username"]').fill('test');
	await page.locator('input[name="password"]').fill('hunter2');
	await page.getByRole('button', { name: /^login$/i }).click();
	await expect(page).toHaveURL('/home');
}

test.describe('reader page', () => {
	test('shows the "not found" message for an unknown score id', async ({ page }) => {
		await login(page);
		await page.goto('/reader/999');
		await expect(page.getByRole('heading', { name: /score not found/i })).toBeVisible();
	});

	test('renders the PDF.js iframe for an owned score', async ({ page }) => {
		await login(page);
		await page.goto('/reader/1');
		await expect(page.getByRole('heading', { name: 'Moonlight Sonata' })).toBeVisible();
		// Smoke check only — the stub backend doesn't serve real PDF bytes, so
		// we just assert the PDF.js iframe is wired up, not its rendered content.
		await expect(page.locator('iframe[title="PDF Viewer"]')).toHaveAttribute(
			'src',
			/\/pdfjs\/web\/viewer\.html\?file=/
		);
	});
});
