<script>
  import { goto } from '$app/navigation';
  import { isAuthenticated } from '$lib/stores/auth.js';
  import { get } from 'svelte/store';
  import { onMount } from 'svelte';

  // onMount only runs on the client, never on the server
  onMount(() => {
    if (get(isAuthenticated)) goto('/dashboard');
    else goto('/login');
  });
</script>