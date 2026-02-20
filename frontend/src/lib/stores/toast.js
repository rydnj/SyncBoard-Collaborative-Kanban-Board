import { writable } from 'svelte/store';

// Each toast: { id, message, type: 'success'|'error'|'info', visible: true }
export const toasts = writable([]);

let nextId = 0;

export function addToast(message, type = 'success', duration = 3000) {
  const id = nextId++;
  toasts.update(t => [...t, { id, message, type, visible: true }]);

  // Start fade-out slightly before removal
  setTimeout(() => {
    toasts.update(t => t.map(toast =>
      toast.id === id ? { ...toast, visible: false } : toast
    ));
    // Remove from DOM after fade-out animation completes
    setTimeout(() => {
      toasts.update(t => t.filter(toast => toast.id !== id));
    }, 300);
  }, duration);
}