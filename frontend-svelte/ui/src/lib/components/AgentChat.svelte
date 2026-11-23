<script lang="ts">
	import { enhance, type ActionResult } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import { Button } from '#lib/components/ui/button/index.js';
	import type { Snippet } from 'svelte';
	import type { User } from '#lib/types.js';
	import * as m from '#lib/paraglide/messages.js';
	import { aiLeftLabel } from '#lib/usage.js';
	import SparklesIcon from '@lucide/svelte/icons/sparkles';
	import ArrowUpIcon from '@lucide/svelte/icons/arrow-up';
	import RotateCcwIcon from '@lucide/svelte/icons/rotate-ccw';

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
		titleClass = 'text-lg font-bold',
		emptyMessage,
		placeholder,
		onResult,
		children,
		resultSnippet,
		user,
		store,
		suggestions = []
	}: {
		form: AgentChatForm | null | undefined;
		action: string;
		title: string;
		/** Classes for the heading (size, font). */
		titleClass?: string;
		emptyMessage?: string;
		placeholder: string;
		onResult: (result: AgentActionData) => ParsedResult;
		children?: Snippet;
		resultSnippet: Snippet<[{ msg: HistoryMessage; isLast: boolean }]>;
		user: User | null | undefined;
		store: HistoryStore;
		/** Example questions shown as buttons while the conversation is empty. */
		suggestions?: string[];
	} = $props();

	let loading = $state(false);
	let pendingQuestion = $state('');
	let scrollContainer: HTMLElement | undefined = $state();
	let formElement: HTMLFormElement | undefined = $state();
	let questionInput: HTMLInputElement | undefined = $state();

	/** Ask a suggested question as if it had been typed. */
	function ask(question: string) {
		if (!questionInput || !formElement || loading) return;
		questionInput.value = question;
		formElement.requestSubmit();
	}

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

	function handleEnhance({ formData }: { formData: FormData }) {
		pendingQuestion = String(formData.get('question') ?? '');
		loading = true;
		return async ({
			result,
			update
		}: {
			result: ActionResult;
			update: (options?: { reset?: boolean }) => Promise<void>;
		}) => {
			loading = false;
			pendingQuestion = '';
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

<div class="flex h-full min-h-0 w-full flex-col">
	{#if store.history.length || loading}
		<div class="mb-3 flex items-center justify-between gap-2">
			<h2 class="text-foreground text-base font-semibold">{title.replace(/[,:]\s*$/, '')}</h2>
			<Button
				variant="ghost"
				size="sm"
				onclick={clearHistory}
				disabled={loading}
				class="text-muted-foreground"
			>
				<RotateCcwIcon />{m.clean_history()}
			</Button>
		</div>
	{/if}

	<div
		class="min-h-0 flex-1 overflow-y-auto pr-1 {store.history.length || loading
			? ''
			: 'flex flex-col justify-center'}"
		bind:this={scrollContainer}
		aria-live="polite"
	>
		{#if !store.history.length && !loading}
			<div class="flex flex-col gap-4 py-4">
				<h1 class="text-foreground {titleClass}">
					{title}
					<span class="text-muted-foreground block">{emptyMessage || m.how_can_i_help()}</span>
				</h1>
				{#if suggestions.length}
					<div class="flex flex-wrap gap-2">
						{#each suggestions as suggestion (suggestion)}
							<button
								type="button"
								onclick={() => ask(suggestion)}
								class="border-border bg-background hover:bg-muted hover:border-primary/40 rounded-full border px-3 py-1.5 text-sm transition-colors"
							>
								{suggestion}
							</button>
						{/each}
					</div>
				{/if}
			</div>
		{:else}
			<ol class="flex flex-col gap-4 pb-2">
				{#each store.history as msg, index (index)}
					<li class="flex flex-col gap-3">
						<div class="flex justify-end">
							<p
								class="bg-primary text-primary-foreground max-w-[85%] rounded-2xl rounded-br-sm px-4 py-2 text-sm whitespace-pre-wrap"
							>
								{msg.question}
							</p>
						</div>
						<div class="flex items-start gap-2.5">
							<span
								class="bg-primary/10 text-primary mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full"
								aria-hidden="true"><SparklesIcon class="size-4" /></span
							>
							<div
								class="bg-muted text-foreground max-w-[90%] min-w-0 rounded-2xl rounded-tl-sm px-4 py-3 text-sm"
							>
								{@render resultSnippet({ msg, isLast: index === store.history.length - 1 })}
							</div>
						</div>
					</li>
				{/each}
				{#if loading}
					<li class="flex flex-col gap-3">
						{#if pendingQuestion}
							<div class="flex justify-end">
								<p
									class="bg-primary text-primary-foreground max-w-[85%] rounded-2xl rounded-br-sm px-4 py-2 text-sm"
								>
									{pendingQuestion}
								</p>
							</div>
						{/if}
						<div class="flex items-center gap-2.5">
							<span
								class="bg-primary/10 text-primary flex size-7 shrink-0 items-center justify-center rounded-full"
								aria-hidden="true"><SparklesIcon class="size-4" /></span
							>
							<div
								class="bg-muted flex items-center gap-1 rounded-2xl rounded-tl-sm px-4 py-3"
								role="status"
							>
								<span class="sr-only">{m.thinking()}</span>
								{#each [0, 150, 300] as delay (delay)}
									<span
										class="bg-muted-foreground/60 size-1.5 animate-bounce rounded-full"
										style="animation-delay: {delay}ms"
									></span>
								{/each}
							</div>
						</div>
					</li>
				{/if}
			</ol>
		{/if}
	</div>

	<div class="mt-3">
		<form
			method="POST"
			{action}
			use:enhance={handleEnhance}
			bind:this={formElement}
			class="bg-background focus-within:ring-ring flex items-center gap-2 rounded-xl border p-1.5 pl-3 shadow-sm focus-within:ring-2"
		>
			<input type="hidden" name="message_history" value={JSON.stringify(store.rawHistory)} />
			<input
				name="question"
				{placeholder}
				required
				autocomplete="off"
				bind:this={questionInput}
				aria-label={placeholder}
				class="placeholder:text-muted-foreground min-w-0 flex-1 bg-transparent text-sm outline-none"
			/>
			<Button type="submit" size="icon" disabled={loading} aria-label={m.ask()} title={m.ask()}>
				<ArrowUpIcon />
			</Button>
		</form>

		{#if form?.error}
			<p role="alert" class="text-destructive mt-2 text-sm">{form.error}</p>
		{/if}

		<div
			class="text-muted-foreground mt-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs"
		>
			<div class="flex flex-wrap items-center gap-x-4 gap-y-1">
				{@render children?.()}
				<span>{m.agent_can_make_mistakes()}</span>
			</div>
			{#if aiLeftLabel(user)}
				<span class="font-medium">{aiLeftLabel(user)}</span>
			{/if}
		</div>
	</div>
</div>
