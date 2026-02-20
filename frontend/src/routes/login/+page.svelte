<script>
  import { api } from '$lib/api.js';
  import { PUBLIC_API_URL } from '$env/static/public';  import { login } from '$lib/stores/auth.js';
  import { goto } from '$app/navigation';

  let email = '', password = '', error = '', loading = false;

  async function handleLogin() {
    loading = true; error = '';
    try {
      const res = await api.post('/api/auth/login', { email, password });
      const userRes = await fetch(`${PUBLIC_API_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${res.access_token}` }
      });
      const userData = await userRes.json();
      login(res.access_token, userData);
      goto('/dashboard');
    } catch (e) {
      error = 'Invalid email or password.';
    } finally {
      loading = false;
    }
  }
</script>

<div class="auth-container">
  <div class="auth-card">
    <h1>Welcome back</h1>
    <p class="subtitle">Sign in to SyncBoard</p>

    {#if error}<p class="error">{error}</p>{/if}

    <div class="form">
      <input type="email" placeholder="Email" bind:value={email} />
      <input type="password" placeholder="Password" bind:value={password} />
      <button class="btn-primary" on:click={handleLogin} disabled={loading}>
        {loading ? 'Signing in...' : 'Sign in'}
      </button>
    </div>

    <p class="switch">Don't have an account? <a href="/register">Register</a></p>
  </div>
</div>

<style>
  .auth-container {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .auth-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2.5rem;
    width: 100%;
    max-width: 400px;
  }
  h1 { font-size: 1.8rem; margin-bottom: 0.3rem; }
  .subtitle { color: var(--text-muted); margin-bottom: 1.5rem; }
  .form { display: flex; flex-direction: column; gap: 1rem; }
  .error { color: var(--accent); font-size: 0.9rem; margin-bottom: 0.5rem; }
  .switch { margin-top: 1.2rem; text-align: center; color: var(--text-muted); font-size: 0.9rem; }
</style>