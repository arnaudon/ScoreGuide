<script lang="ts">
	import { resolve } from '$app/paths';
	import * as m from '#lib/paraglide/messages.js';

	const OPERATOR = 'Alexis Arnaudon';
	const EMAIL = 'alexis.arnaudon@scoreguide.ch';
	// Postal address lines (street, postcode and town), shown between the name
	// and the country. Empty until the operator provides one.
	const ADDRESS: string[] = [];
</script>

<svelte:head>
	<title>{m.legal_notice()} · ScoreGuide</title>
</svelte:head>

<div class="mx-auto prose max-w-3xl px-4 py-12 sm:px-6 lg:px-8 dark:prose-invert">
	<h1>{m.legal_notice()}</h1>

	<h2>{m.legal_h_operator()}</h2>
	<address class="not-italic">
		{OPERATOR}<br />
		{#each ADDRESS as line (line)}
			{line}<br />
		{/each}
		{m.legal_country()}<br />
		{m.email()}: <a href="mailto:{EMAIL}">{EMAIL}</a>
	</address>
	<p><a href={resolve('/contact')}>{m.privacy_contact_link()}</a></p>

	<h2>{m.legal_h_hosting()}</h2>
	<p>{m.legal_hosting()}</p>

	<h2>{m.legal_h_content()}</h2>
	<p>{m.legal_content()}</p>

	<h2>{m.legal_h_links()}</h2>
	<p>{m.legal_links()}</p>
</div>
