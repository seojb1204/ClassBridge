import { state } from './state.js';
const key = name => `classbridge:${state.me?.id ?? state.me?.email ?? 'guest'}:${name}`;
export function preference(name, fallback = null) {
  try { return localStorage.getItem(key(name)) ?? fallback; } catch { return fallback; }
}
export function savePreference(name, value) {
  try { localStorage.setItem(key(name), String(value)); } catch { /* storage may be disabled */ }
}
