<script lang="ts">
	import LegalPage from '#lib/components/LegalPage.svelte';
	import MailIcon from '@lucide/svelte/icons/mail';
	import * as m from '#lib/paraglide/messages.js';

	const EMAIL = 'alexis.arnaudon@scoreguide.ch';
</script>

<LegalPage title={m.contact()}>
	<p>{m.contact_page_desc()}</p>
	<p class="not-prose">
		<a
			href="mailto:{EMAIL}"
			class="border-border bg-card text-primary hover:bg-secondary inline-flex items-center gap-3 rounded-lg border px-4 py-3 font-medium shadow-sm transition-colors"
		>
			<MailIcon class="size-5" />
			{EMAIL}
		</a>
	</p>
</LegalPage>
