<script lang="ts">
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import type { ActionResult } from '@sveltejs/kit';
	import type { Snippet } from 'svelte';
	import type { User } from '$lib/types.js';
	import * as m from '$lib/paraglide/messages.js';

	type HistoryMessage = {
		question: string;
		[key: string]: unknown;
	};

	type HistoryStore = {
		history: HistoryMessage[];
		rawHistory: unknown[];
		clear: () => void;
	};

	type AgentActionData = Record<string, unknown>;
	type ParsedResult = {
		question: string;
		answer: Record<string, unknown>;
		rawHistory?: unknown[];
	};

	// Only `error` is read here, but the parent's `form` carries additional
	// per-page fields (question, scoreDetails, scores, …). Index-typed so we
	// don't lie about what consumers pass in.
	type AgentChatForm = { error?: string; [key: string]: unknown };

	let {
		form,
		action,
		title,
		emptyMessage,
		placeholder,
		onResult,
		children,
		resultSnippet,
		user,
		store
	}: {
		form: AgentChatForm | null | undefined;
		action: string;
		title: string;
		emptyMessage?: string;
		placeholder: string;
		onResult: (result: AgentActionData) => ParsedResult;
		children?: Snippet;
		resultSnippet: Snippet<[{ msg: HistoryMessage; isLast: boolean }]>;
		user: User | null | undefined;
		store: HistoryStore;
	} = $props();

	let loading = $state(false);
	let scrollContainer: HTMLElement | undefined = $state();

	$effect(() => {
		// Register dependencies so the effect re-runs on history/loading change.
		void store.history;
		void loading;
		if (scrollContainer) {
			scrollContainer.scrollTop = scrollContainer.scrollHeight;
		}
	});

	function clearHistory() {
		store.clear();
	}

	function handleEnhance() {
		loading = true;
		return async ({
			result,
			update
		}: {
			result: ActionResult;
			update: (options?: { reset?: boolean }) => Promise<void>;
		}) => {
			loading = false;
			const success = result.type === 'success' && result.data?.success;
			if (success) {
				const data = result.data as AgentActionData;
				const parsed = onResult(data);
				store.history = [
					...store.history,
					{
						question: parsed.question,
						...parsed.answer
					}
				];

				if (parsed.rawHistory) {
					store.rawHistory = parsed.rawHistory;
				}
			}
			await update({ reset: true });
			if (success) {
				await invalidateAll();
			}
		};
	}
</script>

<div
	class="flex h-full w-full flex-col {store.history.length === 0 && !loading
		? 'justify-center'
		: ''}"
>
	<div class="mb-4">
		<h1 class="text-foreground text-lg font-bold">
			{title}{#if store.history.length === 0 && !loading}
				{emptyMessage || m.how_can_i_help()}
			{/if}
		</h1>
	</div>

	<div
		class="space-y-4 overflow-y-auto pr-2 {store.history.length > 0 || loading ? 'mb-4' : ''}"
		bind:this={scrollContainer}
	>
		{#each store.history as msg, index (index)}
			<div class="bg-muted rounded-lg p-4">
				<p class="text-foreground font-bold">{m.q_prefix()} {msg.question}</p>
				{@render resultSnippet({ msg, isLast: index === store.history.length - 1 })}
			</div>
		{/each}
		{#if loading}
			<div class="bg-muted animate-pulse rounded-lg p-4">
				<p class="text-muted-foreground">{m.thinking()}</p>
			</div>
		{/if}
	</div>

	<div
		class="bg-card rounded-lg border p-4 shadow-sm {store.history.length > 0 || loading
			? 'mt-auto'
			: ''}"
	>
		<form method="POST" {action} use:enhance={handleEnhance} class="flex gap-2">
			<input type="hidden" name="message_history" value={JSON.stringify(store.rawHistory)} />
			<Input name="question" {placeholder} required />
			<Button type="submit" disabled={loading}>{m.ask()}</Button>
		</form>

		{#if form?.error}
			<p role="alert" class="text-destructive mt-2 text-sm">{form.error}</p>
		{/if}

		<div class="text-muted-foreground mt-4 flex items-center justify-between text-sm">
			<div class="flex items-center gap-4">
				{@render children?.()}
				<span class="text-xs">{m.agent_can_make_mistakes()}</span>
			</div>
			<div class="flex items-center gap-4">
				{#if user?.credits !== undefined}
					<span class="font-medium"
						>{m.credits_label({ credits: user.credits, max: user.max_credits })}</span
					>
				{/if}
				<Button variant="outline" size="sm" onclick={clearHistory}>{m.clean_history()}</Button>
			</div>
		</div>
	</div>
</div>
