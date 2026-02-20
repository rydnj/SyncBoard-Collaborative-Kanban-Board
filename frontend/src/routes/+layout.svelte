<script>
  import '../app.css';
  import { isAuthenticated, user, logout } from '$lib/stores/auth.js';
  import { goto, invalidateAll } from '$app/navigation';
  import Toast from '$lib/components/Toast.svelte';

  async function handleLogout() {
    logout();
    await invalidateAll();
    window.location.href = '/login';
  }

  // Generate avatar color from display name (deterministic)
  function avatarColor(name) {
    if (!name) return 'var(--accent)';
    const colors = ['#e94560', '#42a5f5', '#66bb6a', '#ffb74d', '#ab47bc', '#26a69a'];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
  }
</script>

{#if $isAuthenticated}
  <nav>
    <a href="/dashboard" class="logo">SyncBoard</a>
    <div class="nav-right">
      <div class="nav-avatar" style="background: {avatarColor($user?.display_name)}">
        {($user?.display_name || '?')[0].toUpperCase()}
      </div>
      <span class="display-name">{$user?.display_name}</span>
      <button class="logout-btn" on:click={handleLogout}>Logout</button>
    </div>
  </nav>
{/if}

<main>
  <slot />
</main>

<Toast />

<style>
  nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1.5rem;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    box-shadow: var(--shadow-sm);
  }
  .logo {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--accent);
    text-decoration: none;
    letter-spacing: -0.3px;
  }
  .nav-right { display: flex; align-items: center; gap: 0.75rem; }
  .nav-avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    font-weight: 700;
    flex-shrink: 0;
  }
  .display-name { color: var(--text-muted); font-size: 0.88rem; }
  .logout-btn {
    background: transparent;
    color: var(--text-muted);
    border: 1px solid var(--border);
    padding: 0.35rem 0.8rem;
    font-size: 0.8rem;
    font-weight: 500;
    border-radius: var(--radius);
  }
  .logout-btn:hover { border-color: var(--text-muted); color: var(--text); background: rgba(255,255,255,0.03); }
  main { padding: 2rem; }
</style>