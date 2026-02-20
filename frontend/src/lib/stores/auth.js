import { writable, derived } from 'svelte/store';

// Load token from localStorage on startup for persistence across page refreshes
const storedToken = typeof localStorage !== 'undefined' ? localStorage.getItem('token') : null;
const storedUser = typeof localStorage !== 'undefined' ? JSON.parse(localStorage.getItem('user') || 'null') : null;

export const token = writable(storedToken);
export const user = writable(storedUser);
export const isAuthenticated = derived(token, $t => !!$t);

// Keep localStorage in sync whenever token/user changes
token.subscribe(val => {
  if (typeof localStorage === 'undefined') return;
  if (val) localStorage.setItem('token', val);
  else localStorage.removeItem('token');
});

user.subscribe(val => {
  if (typeof localStorage === 'undefined') return;
  if (val) localStorage.setItem('user', JSON.stringify(val));
  else localStorage.removeItem('user');
});

export function login(newToken, newUser) {
  token.set(newToken);
  user.set(newUser);
}

export function logout() {
  token.set(null);
  user.set(null);
}