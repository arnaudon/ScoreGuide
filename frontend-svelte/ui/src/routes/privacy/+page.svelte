<script lang="ts">
	import LegalPage from '#lib/components/LegalPage.svelte';
	import { resolve } from '$app/paths';
	import * as m from '#lib/paraglide/messages.js';

	let { data } = $props();

	const host = (h: string) =>
		h === 'infomaniak' ? m.privacy_host_infomaniak() : h === 'google' ? m.privacy_host_google() : h;
</script>

<LegalPage title={m.privacy_policy()} updated={m.privacy_updated()}>
	<p>{m.privacy_intro()}</p>

	<h2>{m.privacy_h_store()}</h2>
	<ul>
		<li>{m.privacy_store_account()}</li>
		<li>{m.privacy_store_library()}</li>
		<li>{m.privacy_store_tech()}</li>
	</ul>

	<h2>{m.privacy_h_where()}</h2>
	<p>{m.privacy_where()}</p>

	<h2>{m.privacy_h_ai()}</h2>
	<p>{m.privacy_ai()}</p>
	{#if data.models.length}
		<p>{m.privacy_models()}</p>
		<ul>
			{#each data.models as model (model.name)}
				<li>
					{m.privacy_model({ name: model.name, vendor: model.vendor, host: host(model.host) })}
				</li>
			{/each}
		</ul>
	{/if}
	<p>{m.privacy_models_note()}</p>

	<h2>{m.privacy_h_email()}</h2>
	<p>{m.privacy_email()}</p>

	<h2>{m.privacy_h_cookies()}</h2>
	<p>{m.privacy_cookies()}</p>

	<h2>{m.privacy_h_share()}</h2>
	<p>{m.privacy_share()}</p>

	<h2>{m.privacy_h_rights()}</h2>
	<p>{m.privacy_rights()}</p>
	<p><a href={resolve('contact')}>{m.privacy_contact_link()}</a></p>
</LegalPage>
