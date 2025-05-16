import { writable } from 'svelte/store';

export function createPersistentStore(key, initialValue) {
  // Try to read from localStorage; if none exists, use the initial value
  const storedValue = localStorage.getItem(key);
  const data = storedValue ? JSON.parse(storedValue) : initialValue;
  const store = writable(data);

  // Subscribe to store changes and write to localStorage
  store.subscribe(value => {
    localStorage.setItem(key, JSON.stringify(value));
  });

  return store;
}
