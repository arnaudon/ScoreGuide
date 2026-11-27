<script lang="ts">
	import LegalPage from '#lib/components/LegalPage.svelte';
	import MailIcon from '@lucide/svelte/icons/mail';
	import CodeIcon from '@lucide/svelte/icons/code-xml';
	import * as m from '#lib/paraglide/messages.js';

	const EMAIL = 'alexis.arnaudon@scoreguide.ch';
	const REPOSITORY = 'https://github.com/arnaudon/ScoreGuide';
	const card =
		'border-border bg-card text-primary hover:bg-secondary inline-flex items-center gap-3 rounded-lg border px-4 py-3 font-medium shadow-sm transition-colors';
</script>

<LegalPage title={m.contact()}>
	<p>{m.contact_page_desc()}</p>
	<p class="not-prose">
		<a href="mailto:{EMAIL}" class={card}>
			<MailIcon class="size-5" />
			{EMAIL}
		</a>
	</p>

	<h2>{m.contact_code_title()}</h2>
	<p>{m.contact_code_desc()}</p>
	<p class="not-prose">
		<a href={REPOSITORY} target="_blank" rel="noopener noreferrer" class={card}>
			<CodeIcon class="size-5" />
			github.com/arnaudon/ScoreGuide
		</a>
	</p>
</LegalPage>
