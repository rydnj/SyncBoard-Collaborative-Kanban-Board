<script>
  import '../app.css';
  import { isAuthenticated, user, logout } from '$lib/stores/auth.js';
  import { goto, invalidateAll } from '$app/navigation';

  async function handleLogout() {
    logout();
    await invalidateAll();
    window.location.href = '/login'; // hard redirect — ensures WS connection is fully torn down
  }
</script>

{#if $isAuthenticated}
  <nav>
    <a href="/dashboard" class="logo">SyncBoard</a>
    <div class="nav-right">
      <span class="display-name">{$user?.display_name}</span>
      <button class="btn-ghost" on:click={handleLogout}>Logout</button>
    </div>
  </nav>
{/if}

<main>
  <slot />
</main>

<style>
  nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.8rem 1.5rem;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }
  .logo { font-size: 1.2rem; font-weight: 700; color: var(--accent); text-decoration: none; }
  .nav-right { display: flex; align-items: center; gap: 1rem; }
  .display-name { color: var(--text-muted); font-size: 0.9rem; }
  main { padding: 2rem; }
</style>