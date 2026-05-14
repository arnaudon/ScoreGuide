<script lang="ts">
	import AgentChat from './AgentChat.svelte';
	import type { User } from '$lib/types.js';

	let {
		title = 'Title',
		emptyMessage = 'How can I help?',
		placeholder = 'ask me anything',
		user = null,
		withHistory = false
	}: {
		title?: string;
		emptyMessage?: string;
		placeholder?: string;
		user?: User | null;
		withHistory?: boolean;
	} = $props();

	type HistoryMessage = { question: string; [key: string]: unknown };

	// svelte-ignore state_referenced_locally
	const store = {
		history: withHistory
			? [{ question: 'find scores', answer: 'found 2 scores' } as HistoryMessage]
			: [],
		rawHistory: [] as unknown[],
		clear() {
			this.history = [];
		}
	};

	function onResult() {
		return { question: '', answer: {} };
	}
</script>

<AgentChat
	form={null}
	action="?/noop"
	{title}
	{emptyMessage}
	{placeholder}
	{onResult}
	{user}
	{store}
>
	{#snippet resultSnippet({ msg }: { msg: HistoryMessage; isLast: boolean })}
		<p>{String(msg.answer ?? '')}</p>
	{/snippet}
</AgentChat>
