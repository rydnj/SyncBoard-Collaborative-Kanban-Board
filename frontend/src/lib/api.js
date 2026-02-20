import { get } from 'svelte/store';
import { token, logout } from './stores/auth.js';

import { PUBLIC_API_URL } from '$env/static/public';
const BASE = PUBLIC_API_URL;

async function request(method, path, body = null) {
  const t = get(token);
  const headers = { 'Content-Type': 'application/json' };
  if (t) headers['Authorization'] = `Bearer ${t}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null
  });

  // Auto-logout on 401 (expired token)
  if (res.status === 401) { logout(); return; }

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  patch: (path, body) => request('PATCH', path, body),
  delete: (path) => request('DELETE', path),
};