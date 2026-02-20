<script>
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api.js';
  import { token, user, isAuthenticated } from '$lib/stores/auth.js';
  import { get } from 'svelte/store';
  import { dndzone } from 'svelte-dnd-action';
  import { flip } from 'svelte/animate';

  import { PUBLIC_WS_URL } from '$env/static/public';

  let room = null, columns = [], activeUsers = [];
  let loading = true, error = '';
  let ws = null, wsConnected = false;
  let reconnectTimeout = null, reconnectAttempts = 0;

  // Card edit modal state
  let editingCard = null, editTitle = '', editDesc = '';

  // New card input state per column
  let addingToColumn = null, newCardTitle = '';

  // ─── Data Loading ───────────────────────────────────────────────────────────

  async function loadBoard() {
    try {
      const data = await api.get(`/api/rooms/${room_id}`);
      room = data;
      // Ensure each column has an items array (svelte-dnd-action needs 'items')
      columns = data.columns.map(col => ({
        ...col,
        items: col.cards.sort((a, b) => a.position - b.position)
      }));
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  // ─── WebSocket ──────────────────────────────────────────────────────────────

  function connectWS() {
    const tok = get(token);
    ws = new WebSocket(`${PUBLIC_WS_URL}/ws/${room_id}?token=${tok}`);

    ws.onopen = () => {
      wsConnected = true;
      reconnectAttempts = 0;
    };

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      handleMessage(msg);
    };

    ws.onclose = () => {
      wsConnected = false;
      scheduleReconnect();
    };

    ws.onerror = () => ws.close();
  }

  function scheduleReconnect() {
    if (reconnectAttempts >= 5) return; // show banner, stop retrying
    const delay = Math.min(1000 * 2 ** reconnectAttempts, 30000);
    reconnectAttempts++;
    reconnectTimeout = setTimeout(() => {
      loadBoard(); // re-fetch state on reconnect to catch missed messages
      connectWS();
    }, delay);
  }

  function handleMessage(msg) {
    switch (msg.type) {
      case 'presence':
        activeUsers = msg.users;
        break;
      case 'user_joined':
        if (!activeUsers.find(u => u.id === msg.user.id))
          activeUsers = [...activeUsers, msg.user];
        break;
      case 'user_left':
        activeUsers = activeUsers.filter(u => u.id !== msg.user_id);
        break;
      case 'card_created':
        columns = columns.map(col =>
          col.id === msg.card.column_id
            ? { ...col, items: [...col.items, msg.card] }
            : col
        );
        break;
      case 'card_moved':
        // Remove from old column, insert at new position
        let movedCard = null;
        columns = columns.map(col => {
          const found = col.items.find(c => c.id === msg.card_id);
          if (found) { movedCard = found; return { ...col, items: col.items.filter(c => c.id !== msg.card_id) }; }
          return col;
        });
        if (movedCard) {
          columns = columns.map(col => {
            if (col.id !== msg.to_column_id) return col;
            const items = [...col.items];
            items.splice(msg.to_position, 0, { ...movedCard, column_id: msg.to_column_id });
            return { ...col, items };
          });
        }
        break;
      case 'card_updated':
        columns = columns.map(col => ({
          ...col,
          items: col.items.map(c =>
            c.id === msg.card_id ? { ...c, title: msg.title, description: msg.description } : c
          )
        }));
        break;
      case 'card_deleted':
        columns = columns.map(col => ({
          ...col,
          items: col.items.filter(c => c.id !== msg.card_id)
        }));
        break;
    }
  }

  function send(msg) {
    if (ws && ws.readyState === WebSocket.OPEN)
      ws.send(JSON.stringify(msg));
  }

  // ─── Card Operations ─────────────────────────────────────────────────────────

  function startAddCard(colId) {
    addingToColumn = colId;
    newCardTitle = '';
  }

  function submitNewCard(colId) {
    if (!newCardTitle.trim()) { addingToColumn = null; return; }
    send({ type: 'card_create', column_id: colId, title: newCardTitle.trim() });
    addingToColumn = null;
    newCardTitle = '';
  }

  function openEdit(card) {
    editingCard = card;
    editTitle = card.title;
    editDesc = card.description || '';
  }

  function saveEdit() {
    if (!editTitle.trim()) return;
    send({ type: 'card_update', card_id: editingCard.id, title: editTitle.trim(), description: editDesc });
    editingCard = null;
  }

  function deleteCard(cardId) {
    send({ type: 'card_delete', card_id: cardId });
    editingCard = null;
  }

  // ─── Drag and Drop ───────────────────────────────────────────────────────────

  function handleDndConsider(colId, e) {
    columns = columns.map(col =>
      col.id === colId ? { ...col, items: e.detail.items } : col
    );
  }

  function handleDndFinalize(colId, e) {
    columns = columns.map(col =>
      col.id === colId ? { ...col, items: e.detail.items } : col
    );
    const card = e.detail.items.find(i => i.id === e.detail.info.id);
    if (!card) return;
    const toPosition = e.detail.items.indexOf(card);
    send({ type: 'card_move', card_id: card.id, to_column_id: colId, to_position: toPosition });
  }

  // ─── Copy room code ──────────────────────────────────────────────────────────

  function copyCode() {
    navigator.clipboard.writeText(room.room_code);
  }

  // ─── Lifecycle ───────────────────────────────────────────────────────────────

  onMount(async () => {
    if (!get(isAuthenticated)) { goto('/login'); return; }
    room_id = $page.params.room_id;
    await loadBoard();
    connectWS();
  });

  onDestroy(() => {
    if (ws) ws.close();
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
  });
</script>

{#if loading}
  <p class="muted center">Loading board...</p>
{:else if error}
  <p class="error center">{error}</p>
{:else}
  <!-- Board Header -->
  <div class="board-header">
    <div class="board-title">
      <h1>{room.name}</h1>
      <button class="code-btn" on:click={copyCode}>
        {room.room_code} 📋
      </button>
    </div>
    <div class="presence">
      {#each activeUsers as u}
        <div class="avatar" title={u.display_name}>
          {u.display_name[0].toUpperCase()}
        </div>
      {/each}
      <span class="ws-dot" class:connected={wsConnected} title={wsConnected ? 'Connected' : 'Disconnected'}></span>
    </div>
  </div>

  {#if !wsConnected && reconnectAttempts >= 5}
    <div class="banner">Connection lost. <button class="btn-ghost" on:click={() => { reconnectAttempts = 0; connectWS(); }}>Retry</button></div>
  {/if}

  <!-- Columns -->
  <div class="board">
    {#each columns as col (col.id)}
      <div class="column">
        <div class="col-header">
          <h2>{col.title}</h2>
          <span class="card-count">{col.items.length}</span>
        </div>

        <!-- DnD zone -->
        <div class="card-list"
          use:dndzone={{ items: col.items, flipDurationMs: 150 }}
          on:consider={(e) => handleDndConsider(col.id, e)}
          on:finalize={(e) => handleDndFinalize(col.id, e)}
        >
          {#each col.items as card (card.id)}
            <div class="card" animate:flip={{ duration: 150 }} on:click={() => openEdit(card)}>
              <p class="card-title">{card.title}</p>
              {#if card.description}<p class="card-desc">{card.description}</p>{/if}
            </div>
          {/each}
        </div>

        <!-- Add card -->
        {#if addingToColumn === col.id}
          <div class="add-card-form">
            <textarea
              placeholder="Card title..."
              bind:value={newCardTitle}
              rows="2"
              on:keydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitNewCard(col.id); }}}
              autofocus
            ></textarea>
            <div class="add-card-actions">
              <button class="btn-primary" on:click={() => submitNewCard(col.id)}>Add</button>
              <button class="btn-ghost" on:click={() => addingToColumn = null}>Cancel</button>
            </div>
          </div>
        {:else}
          <button class="add-card-btn" on:click={() => startAddCard(col.id)}>+ Add card</button>
        {/if}
      </div>
    {/each}
  </div>
{/if}

<!-- Card Edit Modal -->
{#if editingCard}
  <div class="overlay" on:click={() => editingCard = null}>
    <div class="modal" on:click|stopPropagation role="dialog" aria-modal="true">
      <h2>Edit Card</h2>
      <input type="text" bind:value={editTitle} placeholder="Title" />
      <textarea bind:value={editDesc} placeholder="Description (optional)" rows="4"></textarea>
      <div class="modal-actions">
        <button class="btn-ghost danger" on:click={() => deleteCard(editingCard.id)}>Delete</button>
        <div style="display:flex; gap:0.5rem">
          <button class="btn-ghost" on:click={() => editingCard = null}>Cancel</button>
          <button class="btn-primary" on:click={saveEdit}>Save</button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .center { text-align: center; margin-top: 3rem; }
  .muted { color: var(--text-muted); }
  .error { color: var(--accent); }

  .board-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 1.5rem;
  }
  .board-title { display: flex; align-items: center; gap: 1rem; }
  h1 { font-size: 1.4rem; }
  .code-btn {
    background: var(--surface); border: 1px solid var(--border);
    color: var(--text-muted); font-size: 0.8rem; font-family: monospace;
    padding: 0.3rem 0.7rem; border-radius: 4px;
  }

  .presence { display: flex; align-items: center; gap: 0.4rem; }
  .avatar {
    width: 32px; height: 32px; border-radius: 50%;
    background: var(--accent); color: white;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.85rem; font-weight: 700;
  }
  .ws-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--text-muted); margin-left: 0.4rem;
    transition: background 0.3s;
  }
  .ws-dot.connected { background: var(--success); }

  .banner {
    background: #7a3030; color: white; padding: 0.6rem 1rem;
    border-radius: var(--radius); margin-bottom: 1rem;
    display: flex; align-items: center; gap: 1rem;
  }

  .board {
    display: flex; gap: 1rem; align-items: flex-start;
    overflow-x: auto; padding-bottom: 1rem;
  }

  .column {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem;
    min-width: 260px; width: 260px;
    flex-shrink: 0;
  }
  .col-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; }
  .col-header h2 { font-size: 0.95rem; font-weight: 600; }
  .card-count { font-size: 0.75rem; color: var(--text-muted); background: var(--bg); padding: 0.1rem 0.5rem; border-radius: 10px; }

  .card-list { min-height: 80px; display: flex; flex-direction: column; gap: 0.5rem; }

  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.9rem;
    cursor: grab;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .card:hover { border-color: var(--accent); box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
  .card:active { cursor: grabbing; }
  .card-title { font-size: 0.9rem; font-weight: 500; }
  .card-desc { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.3rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .add-card-btn {
    width: 100%; margin-top: 0.5rem; background: transparent;
    color: var(--text-muted); font-size: 0.85rem; font-weight: 500;
    padding: 0.5rem; border-radius: var(--radius);
    border: 1px dashed var(--border); text-align: left;
  }
  .add-card-btn:hover { border-color: var(--accent); color: var(--text); }

  .add-card-form { margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.5rem; }
  .add-card-actions { display: flex; gap: 0.5rem; }

  .overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.6);
    display: flex; align-items: center; justify-content: center; z-index: 100;
  }
  .modal {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 2rem;
    width: 100%; max-width: 420px;
    display: flex; flex-direction: column; gap: 1rem;
  }
  .modal h2 { font-size: 1.1rem; }
  .modal-actions { display: flex; justify-content: space-between; align-items: center; }
  .danger { color: #e57373; border-color: #e57373; }
</style>