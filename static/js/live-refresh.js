// One active page watcher. Never replace a dialog or an input being edited.
let stop = () => {};
export function watchRefresh(root, refresh, onError = () => {}) {
  stop();
  const path = location.hash;
  let running = false;
  async function update() {
    if (running || document.hidden || location.hash !== path || !root.isConnected ||
        document.querySelector('#modal-root [role="dialog"]') ||
        root.querySelector('input:focus, textarea:focus, select:focus')) return;
    running = true;
    try { await refresh(); } catch { onError(); } finally { running = false; }
  }
  const timer = setInterval(update, 30000);
  const changed = () => { if (location.hash !== path) stop(); };
  document.addEventListener('visibilitychange', update);
  window.addEventListener('focus', update);
  window.addEventListener('hashchange', changed);
  stop = () => {
    clearInterval(timer);
    document.removeEventListener('visibilitychange', update);
    window.removeEventListener('focus', update);
    window.removeEventListener('hashchange', changed);
  };
}
