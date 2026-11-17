<!--
	@component
	The scores kept open in the reader, like browser tabs. Remembered in this
	browser; each score also remembers its own page, so switching back picks
	up where you left off.
-->
<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Plus from '@lucide/svelte/icons/plus';
	import X from '@lucide/svelte/icons/x';
	import { closeTab, openTab, parseTabs, type ReaderTab } from '#lib/viewer/tabs.js';
	import * as m from '#lib/paraglide/messages.js';

	let {
		currentId,
		current
	}: {
		/** The score shown now (from the URL). */
		currentId: number;
		/** Its details, or null when it no longer exists. */
		current: ReaderTab | null;
	} = $props();

	const KEY = 'reader.tabs';
	let tabs: ReaderTab[] = $state([]);
	let loaded = $state(false);

	onMount(() => {
		try {
			tabs = parseTabs(localStorage.getItem(KEY));
		} catch {
			// Storage unavailable: tabs last for this visit only.
		}
		loaded = true;
	});

	function save(next: ReaderTab[]) {
		tabs = next;
		try {
			localStorage.setItem(KEY, JSON.stringify(next));
		} catch {
			// Not persisted.
		}
	}

	// Opening a score opens (or refreshes) its tab; a score that's gone loses it.
	$effect(() => {
		if (!loaded) return;
		const shown = current;
		const id = currentId;
		// Read the list untracked: this effect writes it.
		untrack(() => save(shown ? openTab(tabs, shown) : closeTab(tabs, id).tabs));
	});

	function close(id: number) {
		const { tabs: rest, next } = closeTab(tabs, id);
		save(rest);
		if (id !== currentId) return;
		if (next) goto(resolve('/reader/[id]', { id: String(next.id) }));
		else goto(resolve('/db-viewer'));
	}
</script>

{#if tabs.length}
	<nav aria-label={m.reader_tabs()} class="-mx-1 flex min-w-0 items-end gap-1 overflow-x-auto px-1">
		{#each tabs as tab (tab.id)}
			{@const active = tab.id === currentId}
			<div
				class={[
					'group flex max-w-56 min-w-0 shrink-0 items-center rounded-t-md border border-b-0 text-sm transition-colors',
					active
						? 'bg-card text-foreground shadow-card'
						: 'text-muted-foreground hover:bg-accent hover:text-accent-foreground border-transparent'
				]}
			>
				<a
					href={resolve('/reader/[id]', { id: String(tab.id) })}
					aria-current={active ? 'page' : undefined}
					title={`${tab.title} — ${tab.composer}`}
					class="min-w-0 truncate py-1.5 pr-1 pl-3"
				>
					<span class={active ? 'font-semibold' : ''}>{tab.title}</span>
					<span class="text-muted-foreground hidden sm:inline">· {tab.composer}</span>
				</a>
				<button
					type="button"
					onclick={() => close(tab.id)}
					aria-label={m.tab_close({ title: tab.title })}
					title={m.tab_close({ title: tab.title })}
					class="hover:bg-muted mr-1 inline-flex size-6 shrink-0 items-center justify-center rounded-sm"
				>
					<X class="size-3.5" />
				</button>
			</div>
		{/each}
		<a
			href={resolve('/db-viewer')}
			aria-label={m.tab_open_another()}
			title={m.tab_open_another()}
			class="text-muted-foreground hover:bg-accent hover:text-accent-foreground mb-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-md"
		>
			<Plus class="size-4" />
		</a>
	</nav>
{/if}
