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

  // Generate a temporary ID for optimistic updates (replaced by server ID on broadcast)
  function tempId() { return 'temp-' + Math.random().toString(36).slice(2, 11); }

  let room_id = null;
  let room = null, columns = [], activeUsers = [];
  let loading = true, error = '';
  let ws = null, wsConnected = false;
  let reconnectTimeout = null, reconnectAttempts = 0;
  let editingCard = null, editTitle = '', editDesc = '';
  let addingToColumn = null, newCardTitle = '';
  let codeCopied = false;
  let focusedCards = {}; // card_id → { user_id, display_name }
  let confirmDelete = null; // card id pending deletion
  let activityLog = []; // { id, icon, text, time }
  let showActivity = false;

  function addActivity(icon, text) {
    const now = new Date();
    const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    activityLog = [{ id: Date.now(), icon, text, time }, ...activityLog].slice(0, 50);
  }

  function getColTitle(colId) {
    const col = columns.find(c => c.id === colId);
    return col ? col.title : 'unknown';
  }

  function getCardTitle(cardId) {
    for (const col of columns) {
      const card = col.items.find(c => c.id === cardId);
      if (card) return card.title;
    }
    return 'a card';
  }

  function getUserName(userId) {
    const u = activeUsers.find(u => u.id === userId);
    return u ? u.display_name : 'Someone';
  }

  function timeAgo(dateStr) {
    if (!dateStr) return '';
    const now = new Date();
    const d = new Date(dateStr);
    const secs = Math.floor((now - d) / 1000);
    if (secs < 60) return 'just now';
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }

  // Column accent colors by title
  const colColors = { 'To Do': 'var(--col-todo)', 'In Progress': 'var(--col-progress)', 'Done': 'var(--col-done)' };

  let redirecting = false; // prevents rendering after redirect

  async function loadBoard(rid) {
    if (redirecting) return;
    try {
      const data = await api.get(`/api/rooms/${rid}`);
      if (!data) {
        redirecting = true;
        goto('/dashboard');
        return;
      }
      room = data;
      columns = data.columns.map(col => ({
        ...col,
        items: col.cards.sort((a, b) => a.position - b.position)
      }));
      error = '';
    } catch (e) {
      // Room doesn't exist or no access — redirect
      redirecting = true;
      goto('/dashboard');
      return;
    } finally {
      loading = false;
    }
  }

  let reconnecting = false;

  function connectWS(rid) {
    const tok = get(token);
    ws = new WebSocket(`${PUBLIC_WS_URL}/ws/${rid}?token=${tok}`);
    ws.onopen = async () => {
      if (reconnecting) addToast('Back online!', 'success');
      wsConnected = true;
      reconnecting = false;
      reconnectAttempts = 0;
      // Re-fetch board state to ensure consistency after reconnect
      await loadBoard(rid);
    };
    ws.onmessage = (e) => handleMessage(JSON.parse(e.data));
    ws.onclose = () => { wsConnected = false; scheduleReconnect(rid); };
    ws.onerror = () => ws.close();
  }

  function scheduleReconnect(rid) {
    if (redirecting) return;
    if (reconnectAttempts >= 5) {
      reconnecting = false;
      return;
    }
    reconnecting = true;
    const delay = Math.min(1000 * 2 ** reconnectAttempts, 30000);
    reconnectAttempts++;
    reconnectTimeout = setTimeout(async () => {
      if (redirecting) return;
      try {
        const data = await api.get(`/api/rooms/${rid}`);
        if (!data) {
          redirecting = true;
          addToast('Room was deleted', 'info');
          goto('/dashboard');
          return;
        }
        room = data;
        columns = data.columns.map(col => ({
          ...col,
          items: col.cards.sort((a, b) => a.position - b.position)
        }));
        connectWS(rid);
      } catch (e) {
        redirecting = true;
        addToast('Room no longer exists', 'info');
        goto('/dashboard');
      }
    }, delay);
  }

  function handleMessage(msg) {
    switch (msg.type) {
      case 'presence': activeUsers = msg.users; break;
      case 'user_joined':
        if (!activeUsers.find(u => u.id === msg.user.id))
          activeUsers = [...activeUsers, msg.user];
        addActivity('👋', `${msg.user.display_name} joined`);
        break;
      case 'user_left':
        { const name = getUserName(msg.user_id);
        activeUsers = activeUsers.filter(u => u.id !== msg.user_id);
        addActivity('🚪', `${name} left`); }
        break;
      case 'card_created':
        // Check if this is our own card (replace optimistic version)
        { let replaced = false;
        if (pendingCards.size > 0) {
          // Find and replace the temp card in the same column
          columns = columns.map(col => {
            if (col.id !== msg.card.column_id) return col;
            const tempIdx = col.items.findIndex(c => pendingCards.has(c.id) && c.title === msg.card.title);
            if (tempIdx !== -1) {
              replaced = true;
              pendingCards.delete(col.items[tempIdx].id);
              const items = [...col.items];
              items[tempIdx] = msg.card;
              return { ...col, items };
            }
            return col;
          });
        }
        if (!replaced) {
          // Card from another user — just add it
          columns = columns.map(col =>
            col.id === msg.card.column_id ? { ...col, items: [...col.items, msg.card] } : col
          );
        }
        addActivity('✏️', `${getUserName(msg.by)} created "${msg.card.title}"`); }
        break;
      case 'card_moved':
        { const cardTitle = getCardTitle(msg.card_id);
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
        addActivity('↕️', `${getUserName(msg.by)} moved "${cardTitle}" to ${getColTitle(msg.to_column_id)}`); }
        break;
      case 'card_updated':
        columns = columns.map(col => ({
          ...col,
          items: col.items.map(c =>
            c.id === msg.card_id ? { ...c, title: msg.title, description: msg.description } : c
          )
        }));
        addActivity('📝', `${getUserName(msg.by)} updated "${msg.title}"`);
        break;
      case 'card_deleted':
        { const delTitle = getCardTitle(msg.card_id);
        // Remove card (may already be gone if we deleted it optimistically — that's fine)
        columns = columns.map(col => ({
          ...col, items: col.items.filter(c => c.id !== msg.card_id)
        }));
        if (delTitle !== 'a card') addActivity('🗑️', `${getUserName(msg.by)} deleted "${delTitle}"`); }
        break;
      case 'card_focused':
        focusedCards = { ...focusedCards, [msg.card_id]: { user_id: msg.user_id, display_name: msg.display_name } };
        break;
      case 'card_blurred':
        focusedCards = { ...focusedCards };
        delete focusedCards[msg.card_id];
        break;
    }
  }

  function send(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  }

  function startAddCard(colId) { addingToColumn = colId; newCardTitle = ''; }

  let pendingCards = new Set(); // track temp IDs of cards we created optimistically

  function submitNewCard(colId) {
    if (!newCardTitle.trim()) { addingToColumn = null; return; }
    const title = newCardTitle.trim();
    const tid = tempId();

    // Optimistic: add card to UI immediately
    const optimisticCard = { id: tid, column_id: colId, title, description: '', position: 999 };
    columns = columns.map(col =>
      col.id === colId ? { ...col, items: [...col.items, optimisticCard] } : col
    );
    pendingCards.add(tid);

    send({ type: 'card_create', column_id: colId, title });
    addingToColumn = null; newCardTitle = '';
  }

  function openEdit(card) {
    editingCard = card; editTitle = card.title; editDesc = card.description || '';
    send({ type: 'card_focus', card_id: card.id });
  }

  function closeEdit() {
    if (editingCard) send({ type: 'card_blur', card_id: editingCard.id });
    editingCard = null;
  }

  function saveEdit() {
    if (!editTitle.trim()) return;
    send({ type: 'card_update', card_id: editingCard.id, title: editTitle.trim(), description: editDesc });
    closeEdit();
  }

  function askDelete(cardId) {
    confirmDelete = cardId;
  }

  function confirmDeleteCard() {
    if (!confirmDelete) return;
    // Optimistic: remove from UI immediately
    columns = columns.map(col => ({
      ...col, items: col.items.filter(c => c.id !== confirmDelete)
    }));
    send({ type: 'card_delete', card_id: confirmDelete });
    if (editingCard) send({ type: 'card_blur', card_id: editingCard.id });
    editingCard = null;
    confirmDelete = null;
    addToast('Card deleted', 'info');
  }

  function cancelDelete() {
    confirmDelete = null;
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
    if (e.key === 'Escape') { closeEdit(); addingToColumn = null; confirmDelete = null; }
    // N to add card to first column (only when not editing/typing)
    if (e.key === 'n' && !editingCard && !addingToColumn && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
      e.preventDefault();
      if (columns.length > 0) startAddCard(columns[0].id);
    }
  }

  onMount(async () => {
    if (!get(isAuthenticated)) { goto('/login'); return; }
    room_id = get(page).params.room_id;
    await loadBoard(room_id);
    // Only connect WS if board loaded successfully (room exists and we have access)
    if (room && !redirecting) connectWS(room_id);
  });

  onDestroy(() => {
    reconnectAttempts = 5; // prevent any pending reconnect from firing
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
    if (ws) ws.close();
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
{:else if !room}
  <p class="muted center">Redirecting...</p>
{:else}
  <div class="board-header">
    <div class="board-title">
      <h1>{room.name}</h1>
      <button class="code-btn" on:click={copyCode}>
        <span class="code-text">{room.room_code}</span>
        <span class="code-icon">{codeCopied ? '✓' : '📋'}</span>
      </button>
      <span class="total-cards">{columns.reduce((sum, c) => sum + c.items.length, 0)} cards</span>
    </div>
    <div class="presence">
      <button class="activity-toggle" class:active={showActivity} on:click={() => showActivity = !showActivity}
              title="Activity feed">
        📜 {#if activityLog.length > 0}<span class="activity-badge">{activityLog.length}</span>{/if}
      </button>
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

  {#if reconnecting}
    <div class="banner reconnecting">
      <span class="reconnect-spinner"></span>
      Reconnecting... (attempt {reconnectAttempts} of 5)
    </div>
  {:else if !wsConnected && reconnectAttempts >= 5}
    <div class="banner">
      ⚠ Connection lost.
      <button class="btn-ghost" on:click={() => { reconnectAttempts = 0; reconnecting = true; connectWS(room_id); }}>Retry</button>
    </div>
  {/if}

  <div class="board">
    {#if columns.every(col => col.items.length === 0)}
      <div class="board-empty">
        <p class="empty-icon">📋</p>
        <p class="empty-title">Board is empty</p>
        <p class="empty-sub">Press <kbd>N</kbd> or click "+ Add card" to create your first card</p>
      </div>
    {/if}
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
            <div class="card" class:card-focused={focusedCards[card.id]}
                 animate:flip={{ duration: 150 }} on:click={() => openEdit(card)} on:keydown={(e) => { if (e.key === 'Enter') openEdit(card); }} role="button" tabindex="0">
              <p class="card-title">{card.title}</p>
              {#if card.description}<p class="card-desc">{card.description}</p>{/if}
              <div class="card-meta">
                {#if card.created_by}
                  <span class="card-creator" title={getUserName(card.created_by)}>{getUserName(card.created_by)[0].toUpperCase()}</span>
                {/if}
                {#if card.created_at}
                  <span class="card-time">{timeAgo(card.created_at)}</span>
                {/if}
              </div>
              {#if focusedCards[card.id]}
                <p class="editing-label">{focusedCards[card.id].display_name} is editing...</p>
              {/if}
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

  {#if showActivity}
    <div class="activity-panel">
      <div class="activity-header">
        <h3>Activity</h3>
        <button class="activity-close" on:click={() => showActivity = false}>✕</button>
      </div>
      {#if activityLog.length === 0}
        <p class="activity-empty">No activity yet</p>
      {:else}
        <div class="activity-list">
          {#each activityLog as entry (entry.id)}
            <div class="activity-item">
              <span class="activity-icon">{entry.icon}</span>
              <span class="activity-text">{entry.text}</span>
              <span class="activity-time">{entry.time}</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
{/if}

{#if editingCard}
  <div class="overlay" on:click={closeEdit} on:keydown={(e) => { if (e.key === 'Escape') closeEdit(); }} role="button" tabindex="0">
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="modal" on:click|stopPropagation role="dialog" aria-modal="true" tabindex="-1">
      <h2>Edit Card</h2>
      <input type="text" bind:value={editTitle} placeholder="Title"
             on:keydown={(e) => { if (e.key === 'Enter') saveEdit(); }} />
      <textarea bind:value={editDesc} placeholder="Description (optional)" rows="4"></textarea>
      <div class="modal-actions">
        <button class="btn-ghost danger" on:click={() => askDelete(editingCard.id)}>Delete</button>
        <div style="display:flex; gap:0.5rem">
          <button class="btn-ghost" on:click={closeEdit}>Cancel</button>
          <button class="btn-primary" on:click={saveEdit}>Save</button>
        </div>
      </div>
    </div>
  </div>
{/if}

{#if confirmDelete}
  <div class="overlay" on:click={cancelDelete} on:keydown={(e) => { if (e.key === 'Escape') cancelDelete(); }} role="button" tabindex="0">
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="modal confirm-modal" on:click|stopPropagation role="dialog" aria-modal="true" tabindex="-1">
      <h2>Delete card?</h2>
      <p class="confirm-text">This action cannot be undone.</p>
      <div class="modal-actions" style="justify-content: flex-end;">
        <button class="btn-ghost" on:click={cancelDelete}>Cancel</button>
        <button class="btn-primary danger-btn" on:click={confirmDeleteCard}>Delete</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .center { text-align: center; margin-top: 3rem; }
  .muted { color: var(--text-muted); }
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
    gap: 0.75rem;
    font-size: 0.9rem;
    box-shadow: var(--shadow-sm);
    animation: fadeIn 0.3s ease;
  }
  .banner.reconnecting { background: #5a4a1a; }
  .reconnect-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Board layout */
  .board {
    display: flex;
    gap: 1rem;
    align-items: stretch;
    overflow-x: auto;
    padding-bottom: 1rem;
    min-height: calc(100vh - 160px);
  }

  /* Columns */
  .column {
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 3px solid var(--col-accent, var(--accent));
    border-radius: var(--radius);
    padding: 1rem;
    min-width: 320px;
    width: 320px;
    flex-shrink: 0;
    box-shadow: var(--shadow-sm);
    display: flex;
    flex-direction: column;
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
  .card-list { min-height: 60px; display: flex; flex-direction: column; gap: 0.5rem; flex: 1; }
  /* DnD placeholder styling — svelte-dnd-action adds this class */
  .card-list :global(.dnd-shadow-placeholder) {
    background: rgba(233, 69, 96, 0.08) !important;
    border: 2px dashed var(--accent) !important;
    border-radius: var(--radius);
  }
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
  .card-focused {
    border-color: var(--warning) !important;
    box-shadow: 0 0 0 1px var(--warning), var(--shadow-sm) !important;
  }
  .editing-label {
    font-size: 0.7rem;
    color: var(--warning);
    margin-top: 0.4rem;
    font-style: italic;
  }
  .card-title { font-size: 0.9rem; font-weight: 500; }
  .card-desc {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.3rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .card-meta {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-top: 0.5rem;
  }
  .card-creator {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--border);
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.6rem;
    font-weight: 700;
  }
  .card-time {
    font-size: 0.68rem;
    color: var(--text-muted);
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
  .danger-btn { background: #c62828; }
  .danger-btn:hover { background: #b71c1c; box-shadow: none; }
  .confirm-modal { max-width: 340px; }
  .confirm-text { color: var(--text-muted); font-size: 0.9rem; }
  .total-cards { font-size: 0.8rem; color: var(--text-muted); font-weight: 500; }
  .board-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    padding: 3rem;
    text-align: center;
  }
  .board-empty .empty-icon { font-size: 2.5rem; margin-bottom: 0.8rem; }
  .board-empty .empty-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 0.3rem; }
  .board-empty .empty-sub { color: var(--text-muted); font-size: 0.85rem; }
  .board-empty kbd {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.1rem 0.4rem;
    font-size: 0.8rem;
    font-family: monospace;
  }

  /* Activity feed */
  .activity-toggle {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-muted);
    padding: 0.3rem 0.6rem;
    border-radius: 6px;
    font-size: 0.85rem;
    margin-right: 0.75rem;
    position: relative;
    transition: border-color var(--transition), background var(--transition);
  }
  .activity-toggle:hover, .activity-toggle.active { border-color: var(--accent); color: var(--text); }
  .activity-badge {
    position: absolute;
    top: -6px;
    right: -6px;
    background: var(--accent);
    color: white;
    font-size: 0.6rem;
    font-weight: 700;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .activity-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 300px;
    height: 100vh;
    background: var(--surface);
    border-left: 1px solid var(--border);
    box-shadow: var(--shadow-lg);
    z-index: 50;
    display: flex;
    flex-direction: column;
    animation: slideIn 0.2s ease;
  }
  @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
  .activity-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.2rem;
    border-bottom: 1px solid var(--border);
  }
  .activity-header h3 { font-size: 1rem; font-weight: 600; }
  .activity-close {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 1rem;
    padding: 0.2rem 0.4rem;
    cursor: pointer;
  }
  .activity-close:hover { color: var(--text); }
  .activity-empty { color: var(--text-muted); font-size: 0.85rem; padding: 2rem 1.2rem; text-align: center; }
  .activity-list { overflow-y: auto; flex: 1; padding: 0.5rem 0; }
  .activity-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.6rem 1.2rem;
    font-size: 0.82rem;
    border-bottom: 1px solid rgba(255,255,255,0.03);
    animation: fadeIn 0.2s ease;
  }
  .activity-item:hover { background: rgba(255,255,255,0.02); }
  .activity-icon { flex-shrink: 0; font-size: 0.85rem; }
  .activity-text { flex: 1; color: var(--text); line-height: 1.4; }
  .activity-time { flex-shrink: 0; color: var(--text-muted); font-size: 0.7rem; margin-top: 1px; }
</style>