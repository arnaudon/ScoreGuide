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
	plan: 'free',
	usage: {
		plan: 'free',
		ai_used: 50,
		ai_allowance: 200,
		storage_used: 0,
		storage_limit: 0
	},
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

	it('shows how much AI allowance is left when user is supplied', async () => {
		render(AgentChatHarness, { user: USER, withHistory: false });
		await expect.element(page.getByText('AI: 75% left')).toBeInTheDocument();
	});

	it('shows the question and the answer of each exchange', async () => {
		render(AgentChatHarness, { withHistory: true });
		await expect.element(page.getByText(/find scores/i)).toBeInTheDocument();
		await expect.element(page.getByText(/found 2 scores/i)).toBeInTheDocument();
	});

	it('offers to clean the history only once there is a conversation', async () => {
		render(AgentChatHarness, { withHistory: false });
		await expect
			.element(page.getByRole('button', { name: /clean history/i }))
			.not.toBeInTheDocument();
		render(AgentChatHarness, { withHistory: true });
		await expect.element(page.getByRole('button', { name: /clean history/i })).toBeInTheDocument();
	});

	it('shows example questions while the conversation is empty', async () => {
		render(AgentChatHarness, { suggestions: ['Surprise me', 'A piece by Bach'] });
		await expect.element(page.getByRole('button', { name: 'Surprise me' })).toBeInTheDocument();
		await expect.element(page.getByRole('button', { name: 'A piece by Bach' })).toBeInTheDocument();
	});

	it('hides the examples once there is a conversation', async () => {
		render(AgentChatHarness, { withHistory: true, suggestions: ['Surprise me'] });
		await expect.element(page.getByText(/found 2 scores/i)).toBeInTheDocument();
		await expect.element(page.getByRole('button', { name: 'Surprise me' })).not.toBeInTheDocument();
	});
});
