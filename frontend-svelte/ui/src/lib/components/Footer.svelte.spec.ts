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

	it('hides the language toggle by default', async () => {
		render(Footer);
		await expect
			.element(page.getByRole('button', { name: /switch to english/i }))
			.not.toBeInTheDocument();
	});

	it('shows the language toggle when showLanguageToggle is true', async () => {
		render(Footer, { showLanguageToggle: true });
		await expect
			.element(page.getByRole('button', { name: /switch to english/i }))
			.toBeInTheDocument();
		await expect
			.element(page.getByRole('button', { name: /switch to french/i }))
			.toBeInTheDocument();
		await expect.element(page.getByRole('group', { name: /language/i })).toBeInTheDocument();
	});
});
