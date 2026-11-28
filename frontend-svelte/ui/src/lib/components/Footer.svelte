<script lang="ts">
	import { resolve } from '$app/paths';
	import LanguagePicker from './LanguagePicker.svelte';
	import ReportBug from './ReportBug.svelte';
	import * as m from '#lib/paraglide/messages.js';

	let { showLanguageToggle = false }: { showLanguageToggle?: boolean } = $props();
</script>

<footer class="text-muted-foreground p-4 text-sm">
	{#if showLanguageToggle}
		<div class="mb-4 flex justify-center">
			<LanguagePicker />
		</div>
	{/if}
	<div class="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
		<a href={resolve('terms')} class="hover:underline">{m.terms_of_service()}</a>
		<a href={resolve('privacy')} class="hover:underline">{m.privacy_policy()}</a>
		<a href={resolve('legal')} class="hover:underline">{m.legal_notice()}</a>
		<a href={resolve('contact')} class="hover:underline">{m.contact()}</a>
		<ReportBug />
		<span>© 2026 Alexis Arnaudon</span>
	</div>
</footer>
