import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import AgentChatHarness from './AgentChatHarness.test.svelte';

const USER = {
	id: 1,
	username: 'alice',
	email: null,
	first_name: null,
	last_name: null,
	instrument: null,
	role: 'user',
	credits: 7,
	max_credits: 20,
	last_login: null
};

describe('AgentChat.svelte', () => {
	it('renders the title and shows the empty-state hint when history is empty', async () => {
		render(AgentChatHarness, {
			title: 'Hello',
			emptyMessage: 'what next?',
			withHistory: false
		});
		await expect.element(page.getByText(/^Hello/)).toBeInTheDocument();
		await expect.element(page.getByText(/what next/i)).toBeInTheDocument();
	});

	it('renders the prompt input and submit button', async () => {
		render(AgentChatHarness, { title: 'Hi', placeholder: 'ask me', withHistory: false });
		await expect.element(page.getByPlaceholder(/ask me/)).toBeInTheDocument();
		await expect.element(page.getByRole('button', { name: /^ask$/i })).toBeInTheDocument();
	});

	it('shows the credits badge when user is supplied', async () => {
		render(AgentChatHarness, { user: USER, withHistory: false });
		await expect.element(page.getByText(/7\s*\/\s*20/)).toBeInTheDocument();
	});

	it('renders each Q: prefix and the result snippet for history entries', async () => {
		render(AgentChatHarness, { withHistory: true });
		await expect.element(page.getByText(/find scores/i)).toBeInTheDocument();
		await expect.element(page.getByText(/found 2 scores/i)).toBeInTheDocument();
	});

	it('exposes a clean-history button', async () => {
		render(AgentChatHarness, { withHistory: false });
		await expect.element(page.getByRole('button', { name: /clean history/i })).toBeInTheDocument();
	});
});
