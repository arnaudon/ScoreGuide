<script lang="ts">
	import { getLocale, locales, setLocale } from '#lib/paraglide/runtime.js';
	import * as m from '#lib/paraglide/messages.js';

	/** Language menu (each language in its own name); switching reloads the page. */
	let { compact = false, class: className = '' }: { compact?: boolean; class?: string } = $props();

	const NAMES: Record<string, string> = {
		fr: 'Français',
		en: 'English',
		de: 'Deutsch',
		it: 'Italiano'
	};
	type Locale = (typeof locales)[number];
</script>

<label class="inline-flex items-center {className}">
	<span class="sr-only">{m.language_switch()}</span>
	<select
		value={getLocale()}
		onchange={(event) => setLocale(event.currentTarget.value as Locale)}
		title={m.language_switch()}
		class="border-input bg-background hover:bg-muted focus-visible:ring-ring rounded-md border text-xs font-semibold focus-visible:ring-2 focus-visible:outline-none {compact
			? 'h-9 w-11 px-1 text-center uppercase'
			: 'h-8 px-2'}"
	>
		{#each locales as locale (locale)}
			<option value={locale}>{compact ? locale.toUpperCase() : (NAMES[locale] ?? locale)}</option>
		{/each}
	</select>
</label>
