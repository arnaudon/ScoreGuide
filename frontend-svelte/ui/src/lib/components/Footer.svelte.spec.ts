import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import Footer from './Footer.svelte';

describe('Footer.svelte', () => {
	it('renders the always-on links and copyright', async () => {
		render(Footer);
		await expect.element(page.getByRole('link', { name: /terms of service/i })).toBeInTheDocument();
		await expect.element(page.getByRole('link', { name: /privacy policy/i })).toBeInTheDocument();
		await expect.element(page.getByRole('link', { name: /^contact$/i })).toBeInTheDocument();
		await expect.element(page.getByText(/Alexis Arnaudon/)).toBeInTheDocument();
	});

	it('hides the language picker by default', async () => {
		render(Footer);
		await expect.element(page.getByRole('combobox', { name: /language/i })).not.toBeInTheDocument();
	});

	it('offers French, English, German and Italian when showLanguageToggle is true', async () => {
		render(Footer, { showLanguageToggle: true });
		const picker = page.getByRole('combobox', { name: /language/i });
		await expect.element(picker).toBeInTheDocument();
		for (const name of ['Français', 'English', 'Deutsch', 'Italiano']) {
			await expect.element(page.getByRole('option', { name })).toBeInTheDocument();
		}
		await expect.element(picker).toHaveValue('en');
	});
});
