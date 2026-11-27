<script lang="ts">
	import LegalPage from '#lib/components/LegalPage.svelte';
	import * as m from '#lib/paraglide/messages.js';
</script>

<LegalPage title={m.terms_of_service()}>
	<p>{m.terms_p1()}</p>
	<p>{m.terms_p2()}</p>
	<p>{m.terms_p3()}</p>
</LegalPage>
