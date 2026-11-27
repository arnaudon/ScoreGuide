<script lang="ts">
	import LegalPage from '#lib/components/LegalPage.svelte';
	import { resolve } from '$app/paths';
	import * as m from '#lib/paraglide/messages.js';

	const OPERATOR = 'Alexis Arnaudon';
	const EMAIL = 'alexis.arnaudon@scoreguide.ch';
	// Postal address lines (street, postcode and town), shown between the name
	// and the country. Empty until the operator provides one.
	const ADDRESS: string[] = [];
</script>

<LegalPage title={m.legal_notice()}>
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
</LegalPage>
