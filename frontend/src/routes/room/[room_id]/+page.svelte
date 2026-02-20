<script>
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api.js';
  import { token, isAuthenticated } from '$lib/stores/auth.js';
  import { get } from 'svelte/store';
  import { PUBLIC_WS_URL } from '$env/static/public';
  import { dndzone } from 'svelte-dnd-action';
  import { flip } from 'svelte/animate';
  import { addToast } from '$lib/stores/toast.js';

  let room_id = null;
  let room = null, columns = [], activeUsers = [];
  let loading = true, error = '';
  let ws = null, wsConnected = false;
  let reconnectTimeout = null, reconnectAttempts = 0;
  let editingCard = null, editTitle = '', editDesc = '';
  let addingToColumn = null, newCardTitle = '';
  let codeCopied = false;

  // Column accent colors by title
  const colColors = { 'To Do': 'var(--col-todo)', 'In Progress': 'var(--col-progress)', 'Done': 'var(--col-done)' };

  async function loadBoard(rid) {
    try {
      const data = await api.get(`/api/rooms/${rid}`);
      room = data;
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

  function connectWS(rid) {
    const tok = get(token);
    ws = new WebSocket(`${PUBLIC_WS_URL}/ws/${rid}?token=${tok}`);
    ws.onopen = () => {
      wsConnected = true;
      reconnectAttempts = 0;
      if (reconnectAttempts === 0) { /* first connect, no toast */ }
    };
    ws.onmessage = (e) => handleMessage(JSON.parse(e.data));
    ws.onclose = () => {
      const wasConnected = wsConnected;
      wsConnected = false;
      if (wasConnected) scheduleReconnect(rid);
    };
    ws.onerror = () => ws.close();
  }

  function scheduleReconnect(rid) {
    if (reconnectAttempts >= 5) {
      addToast('Connection lost', 'error');
      return;
    }
    const delay = Math.min(1000 * 2 ** reconnectAttempts, 30000);
    reconnectAttempts++;
    reconnectTimeout = setTimeout(async () => {
      await loadBoard(rid);
      connectWS(rid);
    }, delay);
  }

  function handleMessage(msg) {
    switch (msg.type) {
      case 'presence': activeUsers = msg.users; break;
      case 'user_joined':
        if (!activeUsers.find(u => u.id === msg.user.id))
          activeUsers = [...activeUsers, msg.user];
        break;
      case 'user_left':
        activeUsers = activeUsers.filter(u => u.id !== msg.user_id);
        break;
      case 'card_created':
        columns = columns.map(col =>
          col.id === msg.card.column_id ? { ...col, items: [...col.items, msg.card] } : col
        );
        break;
      case 'card_moved':
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
          ...col, items: col.items.filter(c => c.id !== msg.card_id)
        }));
        break;
    }
  }

  function send(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  }

  function startAddCard(colId) { addingToColumn = colId; newCardTitle = ''; }

  function submitNewCard(colId) {
    if (!newCardTitle.trim()) { addingToColumn = null; return; }
    send({ type: 'card_create', column_id: colId, title: newCardTitle.trim() });
    addingToColumn = null; newCardTitle = '';
  }

  function openEdit(card) { editingCard = card; editTitle = card.title; editDesc = card.description || ''; }

  function saveEdit() {
    if (!editTitle.trim()) return;
    send({ type: 'card_update', card_id: editingCard.id, title: editTitle.trim(), description: editDesc });
    editingCard = null;
  }

  function deleteCard(cardId) {
    send({ type: 'card_delete', card_id: cardId });
    editingCard = null;
    addToast('Card deleted', 'info');
  }

  function handleDndConsider(colId, e) {
    columns = columns.map(col => col.id === colId ? { ...col, items: e.detail.items } : col);
  }

  function handleDndFinalize(colId, e) {
    columns = columns.map(col => col.id === colId ? { ...col, items: e.detail.items } : col);
    const card = e.detail.items.find(i => i.id === e.detail.info.id);
    if (!card) return;
    send({ type: 'card_move', card_id: card.id, to_column_id: colId, to_position: e.detail.items.indexOf(card) });
  }

  function copyCode() {
    const code = room.room_code;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(code);
    } else {
      const el = document.createElement('input');
      el.value = code;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    }
    codeCopied = true;
    addToast('Room code copied!', 'success');
    setTimeout(() => { codeCopied = false; }, 1500);
  }

  function avatarColor(name) {
    if (!name) return 'var(--accent)';
    const colors = ['#e94560', '#42a5f5', '#66bb6a', '#ffb74d', '#ab47bc', '#26a69a'];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') { editingCard = null; addingToColumn = null; }
  }

  onMount(async () => {
    if (!get(isAuthenticated)) { goto('/login'); return; }
    room_id = get(page).params.room_id;
    await loadBoard(room_id);
    connectWS(room_id);
  });

  onDestroy(() => {
    if (ws) ws.close();
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
  });
</script>

<svelte:window on:keydown={handleKeydown} />

{#if loading}
  <!-- Skeleton loader -->
  <div class="board-header">
    <div class="board-title">
      <div class="skeleton" style="width:160px; height:1.4rem"></div>
      <div class="skeleton" style="width:90px; height:1.5rem"></div>
    </div>
  </div>
  <div class="board">
    {#each [1, 2, 3] as _}
      <div class="column skeleton-col">
        <div class="skeleton" style="height:1rem; width:60%; margin-bottom:0.8rem"></div>
        <div class="skeleton" style="height:60px; width:100%; margin-bottom:0.5rem"></div>
        <div class="skeleton" style="height:60px; width:100%"></div>
      </div>
    {/each}
  </div>
{:else if error}
  <p class="error center">{error}</p>
{:else}
  <div class="board-header">
    <div class="board-title">
      <h1>{room.name}</h1>
      <button class="code-btn" on:click={copyCode}>
        <span class="code-text">{room.room_code}</span>
        <span class="code-icon">{codeCopied ? '✓' : '📋'}</span>
      </button>
    </div>
    <div class="presence">
      {#each activeUsers as u, i}
        <div class="avatar" style="background: {avatarColor(u.display_name)}; z-index: {activeUsers.length - i};"
             title={u.display_name}>
          {u.display_name[0].toUpperCase()}
        </div>
      {/each}
      <span class="ws-dot" class:connected={wsConnected}
            title={wsConnected ? 'Connected' : 'Disconnected'}></span>
    </div>
  </div>

  {#if !wsConnected && reconnectAttempts >= 5}
    <div class="banner">
      ⚠ Connection lost.
      <button class="btn-ghost" on:click={() => { reconnectAttempts = 0; connectWS(room_id); }}>Retry</button>
    </div>
  {/if}

  <div class="board">
    {#each columns as col (col.id)}
      <div class="column" style="--col-accent: {colColors[col.title] || 'var(--accent)'}">
        <div class="col-header">
          <h2>{col.title}</h2>
          <span class="card-count">{col.items.length}</span>
        </div>

        <div class="card-list"
          use:dndzone={{ items: col.items, flipDurationMs: 150 }}
          on:consider={(e) => handleDndConsider(col.id, e)}
          on:finalize={(e) => handleDndFinalize(col.id, e)}
        >
          {#each col.items as card (card.id)}
            <div class="card" animate:flip={{ duration: 150 }} on:click={() => openEdit(card)} on:keydown={(e) => { if (e.key === 'Enter') openEdit(card); }} role="button" tabindex="0">
              <p class="card-title">{card.title}</p>
              {#if card.description}<p class="card-desc">{card.description}</p>{/if}
            </div>
          {/each}
        </div>

        {#if addingToColumn === col.id}
          <div class="add-card-form">
            <textarea placeholder="Card title..." bind:value={newCardTitle} rows="2"
              on:keydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitNewCard(col.id); }}}
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

{#if editingCard}
  <div class="overlay" on:click={() => editingCard = null} on:keydown={(e) => { if (e.key === 'Escape') editingCard = null; }} role="button" tabindex="0">
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="modal" on:click|stopPropagation role="dialog" aria-modal="true" tabindex="-1">
      <h2>Edit Card</h2>
      <input type="text" bind:value={editTitle} placeholder="Title"
             on:keydown={(e) => { if (e.key === 'Enter') saveEdit(); }} />
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
  .error { color: var(--accent); }

  /* Board Header */
  .board-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
  .board-title { display: flex; align-items: center; gap: 1rem; }
  h1 { font-size: 1.4rem; font-weight: 700; }

  .code-btn {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 0.8rem;
    padding: 0.35rem 0.7rem;
    border-radius: 6px;
    transition: border-color var(--transition), background var(--transition);
  }
  .code-btn:hover { border-color: var(--text-muted); background: rgba(255,255,255,0.03); }
  .code-text { font-family: 'Courier New', monospace; letter-spacing: 0.5px; }
  .code-icon { font-size: 0.85rem; line-height: 1; }

  /* Presence */
  .presence { display: flex; align-items: center; }
  .avatar {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
    font-weight: 700;
    border: 2px solid var(--bg);
    margin-left: -6px;
    transition: transform var(--transition);
    cursor: default;
  }
  .avatar:first-child { margin-left: 0; }
  .avatar:hover { transform: scale(1.1); z-index: 10 !important; }
  .ws-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--text-muted);
    margin-left: 0.6rem;
    transition: background 0.3s;
  }
  .ws-dot.connected {
    background: var(--success);
    animation: dotPulse 2s ease-in-out infinite;
  }

  /* Connection lost banner */
  .banner {
    background: #7a3030;
    color: white;
    padding: 0.6rem 1rem;
    border-radius: var(--radius);
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    font-size: 0.9rem;
    box-shadow: var(--shadow-sm);
    animation: fadeIn 0.3s ease;
  }

  /* Board layout */
  .board { display: flex; gap: 1rem; align-items: flex-start; overflow-x: auto; padding-bottom: 1rem; }

  /* Columns */
  .column {
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 3px solid var(--col-accent, var(--accent));
    border-radius: var(--radius);
    padding: 1rem;
    min-width: 280px;
    width: 280px;
    flex-shrink: 0;
    box-shadow: var(--shadow-sm);
  }
  .skeleton-col {
    border-top-color: var(--border);
    padding: 1rem;
  }
  .col-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; }
  .col-header h2 { font-size: 0.95rem; font-weight: 600; }
  .card-count {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-muted);
    background: var(--bg);
    padding: 0.15rem 0.6rem;
    border-radius: 10px;
    min-width: 24px;
    text-align: center;
  }

  /* Cards */
  .card-list { min-height: 60px; display: flex; flex-direction: column; gap: 0.5rem; }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.9rem;
    cursor: grab;
    box-shadow: var(--shadow-sm);
    transition: border-color var(--transition), box-shadow var(--transition), transform var(--transition);
  }
  .card:hover {
    border-color: var(--accent);
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
  }
  .card:active { cursor: grabbing; }
  .card-title { font-size: 0.9rem; font-weight: 500; }
  .card-desc {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.3rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Add card */
  .add-card-btn {
    width: 100%;
    margin-top: 0.5rem;
    background: transparent;
    color: var(--text-muted);
    font-size: 0.85rem;
    font-weight: 500;
    padding: 0.5rem;
    border-radius: var(--radius);
    border: 1px dashed var(--border);
    text-align: left;
    transition: border-color var(--transition), color var(--transition), background var(--transition);
  }
  .add-card-btn:hover { border-color: var(--accent); color: var(--text); background: rgba(233, 69, 96, 0.05); }
  .add-card-form { margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.5rem; animation: fadeIn 0.2s ease; }
  .add-card-actions { display: flex; gap: 0.5rem; }

  /* Modal overlay */
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
    max-width: 420px;
    display: flex; flex-direction: column; gap: 1rem;
    box-shadow: var(--shadow-lg);
    animation: scaleIn 0.2s ease;
  }
  .modal h2 { font-size: 1.1rem; font-weight: 600; }
  .modal-actions { display: flex; justify-content: space-between; align-items: center; }
  .danger { color: #e57373; border-color: #e57373; }
  .danger:hover { background: rgba(229, 115, 115, 0.1); }
</style>