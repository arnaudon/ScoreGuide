<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from './Sidebar.svelte';
</script>

<Sidebar.Provider>
	<AppSidebar />
</Sidebar.Provider>
