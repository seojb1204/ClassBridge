// No polling. Share successful mutations and invalidate in-flight list snapshots.
import { put } from "./api.js";
let version = 0;
export const inboxVersion = () => version;
export function publishInboxCount(count) {
  window.dispatchEvent(new CustomEvent("inbox-count", { detail: count }));
}
export async function markInboxRead(id) {
  version++;
  try {
    const result = await put(id == null ? "/api/inbox/read-all" : `/api/inbox/${id}/read`);
    version++;
    if (Number.isInteger(result.unread)) publishInboxCount(result.unread);
    window.dispatchEvent(new Event("inbox-changed"));
    try { localStorage.setItem("inbox-refresh", `${Date.now()}:${Math.random()}`); } catch { /* storage optional */ }
    return result;
  } catch (error) { version++; throw error; }
}
window.addEventListener("storage", event => {
  if (event.key === "inbox-refresh") {
    version++;
    window.dispatchEvent(new Event("inbox-changed"));
  }
});
