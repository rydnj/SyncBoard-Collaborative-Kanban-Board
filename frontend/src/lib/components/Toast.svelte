<script>
  import { toasts } from '$lib/stores/toast.js';
</script>

<div class="toast-container">
  {#each $toasts as toast (toast.id)}
    <div class="toast {toast.type}" class:fade-out={!toast.visible}>
      <span class="toast-icon">
        {#if toast.type === 'success'}✓
        {:else if toast.type === 'error'}✕
        {:else}ℹ
        {/if}
      </span>
      <span class="toast-msg">{toast.message}</span>
    </div>
  {/each}
</div>

<style>
  .toast-container {
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    z-index: 200;
    display: flex;
    flex-direction: column-reverse;
    gap: 0.5rem;
    pointer-events: none;
  }

  .toast {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.7rem 1.2rem;
    border-radius: var(--radius);
    font-size: 0.88rem;
    font-weight: 500;
    box-shadow: var(--shadow-md);
    animation: fadeIn 0.25s ease forwards;
    pointer-events: auto;
    max-width: 340px;
  }

  .toast.fade-out {
    animation: fadeOut 0.3s ease forwards;
  }

  .toast.success { background: #1b5e20; color: #c8e6c9; border: 1px solid #2e7d32; }
  .toast.error   { background: #7a1f1f; color: #ffcdd2; border: 1px solid #c62828; }
  .toast.info    { background: #0d47a1; color: #bbdefb; border: 1px solid #1565c0; }

  .toast-icon { font-size: 1rem; line-height: 1; }
  .toast-msg { line-height: 1.3; }
</style>