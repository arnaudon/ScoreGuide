<script lang="ts">
	import { resolve } from '$app/paths';
	import LanguagePicker from './LanguagePicker.svelte';
	import * as m from '#lib/paraglide/messages.js';

	let { showLanguageToggle = false }: { showLanguageToggle?: boolean } = $props();
</script>

<footer class="text-muted-foreground p-4 text-sm">
	{#if showLanguageToggle}
		<div class="mb-4 flex justify-center">
			<LanguagePicker />
		</div>
	{/if}
	<div class="flex flex-col items-center justify-between gap-4 md:flex-row">
		<div class="w-full text-center text-xs md:w-1/3 md:text-left">
			{m.beta_warning()}
			<a href="mailto:alexis.arnaudon@scoreguide.ch" class="text-primary hover:underline"
				>alexis.arnaudon@scoreguide.ch</a
			>.
		</div>

		<div class="flex w-full flex-wrap items-center justify-center gap-x-4 gap-y-2 md:w-1/3">
			<a href={resolve('terms')} class="hover:underline">{m.terms_of_service()}</a>
			<a href={resolve('privacy')} class="hover:underline">{m.privacy_policy()}</a>
			<a href={resolve('contact')} class="hover:underline">{m.contact()}</a>
			<span>© 2026 Alexis Arnaudon</span>
		</div>
		<div class="hidden w-full md:block md:w-1/3"></div>
	</div>
</footer>
