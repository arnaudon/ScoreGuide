<script lang="ts">
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
	import SearchIcon from '@lucide/svelte/icons/search';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import type { ImslpResult, ImslpSearch } from '#lib/types.js';
	import { untrack } from 'svelte';
	import {
		defaultInstrument,
		periodLabel,
		INSTRUMENTS,
		PERIODS,
		instrumentLabel,
		SOLO_FIRST
	} from '#lib/imslp.js';
	import * as m from '#lib/paraglide/messages.js';

	/**
	 * Instant search of the local IMSLP catalogue (no AI, no credits): words
	 * match title, composer, catalogue number and key, ignoring accents. The
	 * instrument filter starts on the user's preferred instrument.
	 */
	let {
		onSelect,
		preferredInstrument = null,
		listClass = '',
		class: className = ''
	}: {
		onSelect: (work: ImslpResult) => void;
		preferredInstrument?: string | null;
		/** Extra classes for the results list, e.g. a max height. */
		listClass?: string;
		/** Extra classes for the root, e.g. `min-h-0 flex-1` to fit a fixed-height box. */
		class?: string;
	} = $props();

	const PAGE = 20;
	let q = $state('');
	let instrument = $state(untrack(() => defaultInstrument(preferredInstrument)));
	// Works for the instrument alone (no duets, songs, chamber music).
	let solo = $state(untrack(() => SOLO_FIRST.has(instrument)));
	let period = $state('');
	let results = $state<ImslpResult[]>([]);
	let total = $state(0);
	let loading = $state(false);
	let failed = $state(false);
	let searched = $state('');
	let controller: AbortController | null = null;

	async function run(offset: number) {
		controller?.abort();
		const ctrl = new AbortController();
		controller = ctrl;
		const fields: Record<string, string> = { q, limit: String(PAGE), offset: String(offset) };
		if (instrument) fields.instrument = instrument;
		if (instrument && solo) fields.solo = 'true';
		if (period) fields.period = period;
		const params = new URLSearchParams(fields).toString();
		loading = true;
		failed = false;
		try {
			const res = await fetch(`/api/imslp/search?${params}`, { signal: ctrl.signal });
			if (!res.ok) throw new Error(String(res.status));
			const page = (await res.json()) as ImslpSearch;
			results = offset ? [...results, ...page.results] : page.results;
			total = page.total;
			searched = q;
		} catch (e) {
			if ((e as Error).name === 'AbortError') return;
			failed = true;
		} finally {
			if (controller === ctrl) loading = false;
		}
	}

	// Search as the user types, a moment after they stop.
	$effect(() => {
		const words = q.trim();
		void instrument;
		void solo;
		void period;
		if (words.length < 2) {
			controller?.abort();
			results = [];
			total = 0;
			searched = '';
			loading = false;
			return;
		}
		const timer = setTimeout(() => run(0), 300);
		return () => clearTimeout(timer);
	});

	/** "Ballade No.2" + "Op.38", unless the title already carries the number. */
	function fullTitle(work: ImslpResult) {
		const cat = work.catalogue.trim();
		return cat && !work.title.includes(cat) ? `${work.title}, ${cat}` : work.title;
	}

	function details(work: ImslpResult) {
		return [work.key, work.year ? String(work.year) : '', work.instrumentation]
			.filter(Boolean)
			.join(' · ');
	}
</script>

<div class="flex min-w-0 flex-col gap-3 {className}">
	<!-- Search on its own line, filters wrap below: the box is narrow on the home page. -->
	<div class="flex min-w-0 flex-col gap-2">
		<div class="relative">
			<SearchIcon
				class="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
				aria-hidden="true"
			/>
			<Input
				type="search"
				bind:value={q}
				placeholder={m.imslp_search_placeholder()}
				aria-label={m.imslp_search_label()}
				class="pl-9"
				autocomplete="off"
			/>
		</div>
		<div class="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2">
			<select
				bind:value={instrument}
				onchange={() => (solo = SOLO_FIRST.has(instrument))}
				aria-label={m.imslp_filter_instrument()}
				class="border-input bg-background focus-visible:ring-ring h-9 max-w-full min-w-0 flex-1 basis-32 rounded-md border px-2 text-sm focus-visible:ring-2 focus-visible:outline-none"
			>
				<option value="">{m.imslp_any_instrument()}</option>
				{#each INSTRUMENTS as value (value)}
					<option {value}>{instrumentLabel(value)}</option>
				{/each}
			</select>
			{#if instrument}
				<label class="flex h-9 items-center gap-1.5 text-sm whitespace-nowrap">
					<input type="checkbox" bind:checked={solo} class="accent-primary size-4" />
					{m.imslp_filter_solo()}
				</label>
			{/if}
			<select
				bind:value={period}
				aria-label={m.imslp_filter_period()}
				class="border-input bg-background focus-visible:ring-ring h-9 max-w-full min-w-0 flex-1 basis-32 rounded-md border px-2 text-sm focus-visible:ring-2 focus-visible:outline-none"
			>
				<option value="">{m.imslp_any_period()}</option>
				{#each PERIODS as value (value)}
					<option {value}>{periodLabel(value)}</option>
				{/each}
			</select>
		</div>
	</div>

	<p class="text-muted-foreground text-xs" role="status" aria-live="polite">
		{#if failed}
			<span class="text-destructive">{m.imslp_search_error()}</span>
		{:else if loading && !results.length}
			{m.imslp_searching()}
		{:else if searched && total === 0}
			{m.imslp_no_results()}
		{:else if searched}
			{m.imslp_results({ count: total })}
		{:else}
			{m.imslp_search_hint()}
		{/if}
	</p>

	{#if results.length}
		<ul class="flex flex-col divide-y rounded-md border {listClass}">
			{#each results as work (work.id)}
				<li class="flex shrink-0 items-center gap-2">
					<button
						type="button"
						class="hover:bg-accent focus-visible:ring-ring flex min-w-0 flex-1 flex-col gap-0.5 px-3 py-2 text-left transition-colors focus-visible:ring-2 focus-visible:outline-none"
						onclick={() => onSelect(work)}
					>
						<span class="flex items-baseline gap-2">
							<span class="text-foreground truncate text-sm font-semibold">{fullTitle(work)}</span>
							{#if work.in_library}
								<span
									class="bg-primary/10 text-primary shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium"
									>{m.imslp_in_library()}</span
								>
							{/if}
						</span>
						<span class="text-muted-foreground truncate text-xs">
							{work.composer}{#if details(work)}&ensp;·&ensp;{details(work)}{/if}
						</span>
					</button>
					<a
						href={work.permlink}
						target="_blank"
						rel="external noopener noreferrer"
						class="text-muted-foreground hover:text-foreground shrink-0 p-2"
						aria-label={m.imslp_open_page({ title: work.title })}
						title={m.imslp_open_page({ title: work.title })}
					>
						<ExternalLinkIcon class="size-4" aria-hidden="true" />
					</a>
				</li>
			{/each}
		</ul>
		{#if results.length < total}
			<Button
				variant="outline"
				size="sm"
				class="self-center"
				disabled={loading}
				onclick={() => run(results.length)}
			>
				{loading ? m.imslp_searching() : m.imslp_more()}
			</Button>
		{/if}
	{/if}
</div>
