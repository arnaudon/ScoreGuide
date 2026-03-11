<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
</script>

<div class="flex h-full items-center justify-center p-8 text-center">
	<div class="max-w-md space-y-4">
		<h1 class="text-2xl font-bold text-foreground">No Score Selected</h1>
		<p class="text-muted-foreground">Please select a score from the database viewer to read it.</p>
		<Button href="/db-viewer">Go to Database Viewer</Button>
	</div>
</div>
