<script>
  import { onMount } from 'svelte';
  import { api } from '$lib/api.js';
  import { goto } from '$app/navigation';
  import { isAuthenticated } from '$lib/stores/auth.js';
  import { get } from 'svelte/store';

  let rooms = [], loading = true, error = '';
  let showCreate = false, showJoin = false;
  let newRoomName = '', joinCode = '', modalError = '';

  onMount(async () => {
    if (!get(isAuthenticated)) { goto('/login'); return; }
    await loadRooms();
  });

  async function loadRooms() {
    try {
      rooms = await api.get('/api/rooms');
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function createRoom() {
    if (!newRoomName.trim()) return;
    modalError = '';
    try {
      const room = await api.post('/api/rooms', { name: newRoomName });
      rooms = [...rooms, room];
      showCreate = false;
      newRoomName = '';
    } catch (e) { modalError = e.message; }
  }

  async function joinRoom() {
    if (!joinCode.trim()) return;
    modalError = '';
    try {
      const room = await api.post('/api/rooms/join', { room_code: joinCode.toUpperCase() });
      if (!rooms.find(r => r.id === room.id)) rooms = [...rooms, room];
      showJoin = false;
      joinCode = '';
    } catch (e) { modalError = e.message; }
  }

  function closeModals() {
    showCreate = false; showJoin = false; modalError = '';
  }
</script>

<div class="dashboard">
  <div class="header">
    <h1>My Boards</h1>
    <div class="actions">
      <button class="btn-ghost" on:click={() => { showJoin = true; showCreate = false; }}>Join Room</button>
      <button class="btn-primary" on:click={() => { showCreate = true; showJoin = false; }}>+ New Room</button>
    </div>
  </div>

  {#if loading}
    <p class="muted">Loading rooms...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if rooms.length === 0}
    <div class="empty">
      <p>No boards yet.</p>
      <p class="muted">Create a new room or join one with a code.</p>
    </div>
  {:else}
    <div class="room-grid">
      {#each rooms as room}
        <div class="room-card" on:click={() => goto(`/room/${room.id}`)} role="button" tabindex="0">
          <h2>{room.name}</h2>
          <div class="room-meta">
            <span class="room-code">{room.room_code}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- Create Room Modal -->
{#if showCreate}
  <div class="overlay" on:click={closeModals}>
    <div class="modal" on:click|stopPropagation>
      <h2>New Room</h2>
      {#if modalError}<p class="error">{modalError}</p>{/if}
      <input type="text" placeholder="Room name" bind:value={newRoomName} />
      <div class="modal-actions">
        <button class="btn-ghost" on:click={closeModals}>Cancel</button>
        <button class="btn-primary" on:click={createRoom}>Create</button>
      </div>
    </div>
  </div>
{/if}

<!-- Join Room Modal -->
{#if showJoin}
  <div class="overlay" on:click={closeModals}>
    <div class="modal" on:click|stopPropagation>
      <h2>Join Room</h2>
      {#if modalError}<p class="error">{modalError}</p>{/if}
      <input type="text" placeholder="Room code (e.g. ESCZV8TA)" bind:value={joinCode} />
      <div class="modal-actions">
        <button class="btn-ghost" on:click={closeModals}>Cancel</button>
        <button class="btn-primary" on:click={joinRoom}>Join</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .dashboard { max-width: 1000px; margin: 0 auto; }
  .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
  .actions { display: flex; gap: 0.8rem; }
  h1 { font-size: 1.6rem; }

  .room-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; }
  .room-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    cursor: pointer;
    transition: border-color 0.2s, transform 0.15s;
  }
  .room-card:hover { border-color: var(--accent); transform: translateY(-2px); }
  .room-card h2 { font-size: 1.1rem; margin-bottom: 0.8rem; }
  .room-code { font-size: 0.75rem; color: var(--text-muted); font-family: monospace; background: var(--bg); padding: 0.2rem 0.5rem; border-radius: 4px; }

  .empty { text-align: center; margin-top: 4rem; }
  .muted { color: var(--text-muted); margin-top: 0.5rem; }
  .error { color: var(--accent); font-size: 0.9rem; margin-bottom: 0.5rem; }

  .overlay {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.6);
    display: flex; align-items: center; justify-content: center;
    z-index: 100;
  }
  .modal {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem;
    width: 100%;
    max-width: 380px;
    display: flex; flex-direction: column; gap: 1rem;
  }
  .modal h2 { font-size: 1.2rem; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 0.8rem; }
</style>