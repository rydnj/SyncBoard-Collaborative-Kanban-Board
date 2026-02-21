<script>
  import { onMount } from 'svelte';
  import { api } from '$lib/api.js';
  import { goto } from '$app/navigation';
  import { isAuthenticated } from '$lib/stores/auth.js';
  import { get } from 'svelte/store';
  import { addToast } from '$lib/stores/toast.js';
  import { user as currentUser } from '$lib/stores/auth.js';

  let rooms = [], loading = true, error = '';
  let showCreate = false, showJoin = false;
  let newRoomName = '', joinCode = '', modalError = '';
  let confirmDeleteRoom = null;

  onMount(async () => {
    if (!get(isAuthenticated)) { goto('/login'); return; }
    await loadRooms(); // Always fetch fresh — rooms may have been deleted
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
      addToast('Room created!', 'success');
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
      addToast('Joined room!', 'success');
    } catch (e) { modalError = e.message; }
  }

  function closeModals() {
    showCreate = false; showJoin = false; modalError = ''; confirmDeleteRoom = null;
  }

  async function deleteRoom(roomId) {
    try {
      await api.delete(`/api/rooms/${roomId}`);
      rooms = rooms.filter(r => r.id !== roomId);
      confirmDeleteRoom = null;
      addToast('Room deleted', 'info');
    } catch (e) {
      confirmDeleteRoom = null;
      addToast(e.message || 'Failed to delete room', 'error');
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') closeModals();
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="dashboard">
  <div class="header">
    <h1>My Boards</h1>
    <div class="actions">
      <button class="btn-ghost" on:click={() => { showJoin = true; showCreate = false; }}>Join Room</button>
      <button class="btn-primary" on:click={() => { showCreate = true; showJoin = false; }}>+ New Room</button>
    </div>
  </div>

  {#if loading}
    <div class="room-grid">
      {#each [1, 2, 3] as _}
        <div class="room-card skeleton-card">
          <div class="skeleton" style="height:1.1rem; width:60%; margin-bottom:0.8rem"></div>
          <div class="skeleton" style="height:0.75rem; width:35%"></div>
        </div>
      {/each}
    </div>
  {:else if error}
    <p class="error">{error}</p>
  {:else if rooms.length === 0}
    <div class="empty">
      <div class="empty-icon">📋</div>
      <p class="empty-title">No boards yet</p>
      <p class="empty-sub">Create a new room or join one with a code to get started.</p>
    </div>
  {:else}
    <div class="room-grid">
      {#each rooms as room, i}
        <div class="room-card" on:click={() => goto(`/room/${room.id}`)} on:keydown={(e) => { if (e.key === 'Enter') goto(`/room/${room.id}`); }} role="button" tabindex="0"
             style="animation-delay: {i * 0.05}s">
          <div class="room-card-top">
            <h2>{room.name}</h2>
            {#if room.created_by === $currentUser?.id}
              <!-- svelte-ignore a11y-click-events-have-key-events -->
              <span class="room-delete" role="button" tabindex="0"
                    on:click|stopPropagation={() => confirmDeleteRoom = room} title="Delete room">✕</span>
            {/if}
          </div>
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
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="overlay" on:click={closeModals}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="modal" on:click|stopPropagation>
      <h2>New Room</h2>
      {#if modalError}<p class="error">{modalError}</p>{/if}
      <input type="text" placeholder="Room name" bind:value={newRoomName}
             on:keydown={(e) => { if (e.key === 'Enter') createRoom(); }} />
      <div class="modal-actions">
        <button class="btn-ghost" on:click={closeModals}>Cancel</button>
        <button class="btn-primary" on:click={createRoom}>Create</button>
      </div>
    </div>
  </div>
{/if}

<!-- Join Room Modal -->
{#if showJoin}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="overlay" on:click={closeModals}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="modal" on:click|stopPropagation>
      <h2>Join Room</h2>
      {#if modalError}<p class="error">{modalError}</p>{/if}
      <input type="text" placeholder="Room code (e.g. ESCZV8TA)" bind:value={joinCode}
             on:keydown={(e) => { if (e.key === 'Enter') joinRoom(); }} />
      <div class="modal-actions">
        <button class="btn-ghost" on:click={closeModals}>Cancel</button>
        <button class="btn-primary" on:click={joinRoom}>Join</button>
      </div>
    </div>
  </div>
{/if}

{#if confirmDeleteRoom}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="overlay" on:click={() => confirmDeleteRoom = null}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="modal" on:click|stopPropagation>
      <h2>Delete "{confirmDeleteRoom.name}"?</h2>
      <p class="delete-warn">This will permanently delete the room and all its cards. This cannot be undone.</p>
      <div class="modal-actions">
        <button class="btn-ghost" on:click={() => confirmDeleteRoom = null}>Cancel</button>
        <button class="btn-primary danger-btn" on:click={() => deleteRoom(confirmDeleteRoom.id)}>Delete Room</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .dashboard { max-width: 1000px; margin: 0 auto; }
  .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
  .actions { display: flex; gap: 0.8rem; }
  h1 { font-size: 1.6rem; font-weight: 700; }

  .room-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; }

  .room-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: var(--radius);
    padding: 1.5rem;
    cursor: pointer;
    box-shadow: var(--shadow-sm);
    transition: border-color var(--transition), transform var(--transition), box-shadow var(--transition);
    animation: fadeIn 0.3s ease backwards;
  }
  .room-card:hover {
    border-color: var(--accent);
    transform: translateY(-3px);
    box-shadow: var(--shadow-md);
  }
  .room-card h2 { font-size: 1.1rem; margin-bottom: 0.8rem; font-weight: 600; }
  .room-card-top { display: flex; justify-content: space-between; align-items: flex-start; }
  .room-card-top h2 { margin-bottom: 0.8rem; font-size: 1.1rem; font-weight: 600; }
  .room-delete {
    color: var(--text-muted);
    font-size: 0.85rem;
    padding: 0.1rem 0.3rem;
    border-radius: 4px;
    cursor: pointer;
    transition: color var(--transition), background var(--transition);
  }
  .room-delete:hover { color: #e57373; background: rgba(229, 115, 115, 0.1); }
  .room-code {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-family: 'Courier New', monospace;
    background: var(--bg);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    letter-spacing: 0.5px;
  }

  .skeleton-card {
    border-left-color: var(--border);
    cursor: default;
    pointer-events: none;
  }

  .empty { text-align: center; margin-top: 4rem; }
  .empty-icon { font-size: 2.5rem; margin-bottom: 0.8rem; }
  .empty-title { font-size: 1.2rem; font-weight: 600; margin-bottom: 0.3rem; }
  .empty-sub { color: var(--text-muted); font-size: 0.9rem; }
  .error { color: var(--accent); font-size: 0.9rem; margin-bottom: 0.5rem; }

  .overlay {
    position: fixed; inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex; align-items: center; justify-content: center;
    z-index: 100;
    animation: fadeIn 0.15s ease;
  }
  .modal {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem;
    width: 100%;
    max-width: 380px;
    display: flex; flex-direction: column; gap: 1rem;
    box-shadow: var(--shadow-lg);
    animation: scaleIn 0.2s ease;
  }
  .modal h2 { font-size: 1.2rem; }
  .modal-actions { display: flex; justify-content: flex-end; gap: 0.8rem; }
  .delete-warn { color: var(--text-muted); font-size: 0.88rem; line-height: 1.4; }
  .danger-btn { background: #c62828; }
  .danger-btn:hover { background: #b71c1c; }
</style>