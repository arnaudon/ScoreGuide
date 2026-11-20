<script lang="ts">
	import { resolve } from '$app/paths';
	import * as m from '#lib/paraglide/messages.js';
</script>

<svelte:head>
	<title>{m.privacy_policy()} · ScoreGuide</title>
</svelte:head>

<div class="mx-auto prose max-w-3xl px-4 py-12 sm:px-6 lg:px-8 dark:prose-invert">
	<h1>{m.privacy_policy()}</h1>
	<p class="text-muted-foreground text-sm">{m.privacy_updated()}</p>
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

	<h2>{m.privacy_h_email()}</h2>
	<p>{m.privacy_email()}</p>

	<h2>{m.privacy_h_cookies()}</h2>
	<p>{m.privacy_cookies()}</p>

	<h2>{m.privacy_h_share()}</h2>
	<p>{m.privacy_share()}</p>

	<h2>{m.privacy_h_rights()}</h2>
	<p>{m.privacy_rights()}</p>
	<p><a href={resolve('contact')}>{m.privacy_contact_link()}</a></p>
</div>
