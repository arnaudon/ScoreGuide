<script lang="ts">
	import { resolve } from '$app/paths';
	import * as m from '$lib/paraglide/messages.js';
</script>

<h1 class="mb-4 text-2xl font-bold">ScoreGuide</h1>

<a href={resolve('/login')} class="text-primary hover:underline">{m.login()}</a>
