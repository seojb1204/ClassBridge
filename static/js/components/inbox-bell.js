// Explicit refresh only. Never keep the database awake with background polling.
import { navIcon } from "./nav-icon.js";
import { get } from "../api.js";
import { h, mount, toast } from "../ui.js";

import { inboxVersion, markInboxRead, publishInboxCount } from "../inbox-state.js";

export function inboxBell() {
  const badge = h("span", { class: "inbox-badge", "aria-hidden": "true", hidden: true });
  const button = h("button", { class: "btn inbox-bell", type: "button", "aria-label": "알림 열기",
    "aria-expanded": "false", "aria-controls": "inbox-popover" }, navIcon("/inbox"), " 알림", badge);
  const panel = h("section", { id: "inbox-popover", class: "inbox-popover", hidden: true,
    "aria-label": "알림 모아보기" }, h("p", { role: "status" }, "알림을 불러오는 중…"));
  const wrap = h("div", { class: "inbox-header" }, button, panel);
  let pending = false, refreshAgain = false, panelVersion = 0;
  const close = (focus = false) => { panelVersion++; panel.hidden = true; button.setAttribute("aria-expanded", "false"); if (focus) button.focus(); };
  const setCount = count => {
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.hidden = !count;
    button.setAttribute("aria-label", count ? `알림 열기, 읽지 않은 알림 ${count}건` : "알림 열기");
  };
  async function refresh() {
    if (pending) { refreshAgain = true; return; }
    pending = true;
    const version = inboxVersion();
    try {
      const data = await get("/api/inbox?limit=5");
      if (version !== inboxVersion()) { refreshAgain = true; return; }
      publishInboxCount(data.unread);
      const refreshButton = h("button", { class: "btn small", type: "button", onclick: refresh }, "새로고침");
      const readAll = h("button", { class: "btn small", type: "button", disabled: !data.unread }, "모두 읽음");
      readAll.onclick = async () => {
        readAll.disabled = true;
        try { await markInboxRead(null); }
        catch (err) { readAll.disabled = false; toast(err.message, "error"); }
      };
      mount(panel, h("div", { class: "inbox-popover-head" }, h("h2", {}, "알림 모아보기"),
        h("button", { class: "btn small", type: "button", onclick: () => close(true) }, "닫기")),
        h("p", { class: "hint" }, `읽지 않은 알림 ${data.unread}건 · 최근 도착순 · 내용 확인 시 읽음 처리`),
        ...data.items.slice(0, 5).map(item => {
          const read = h("button", { class: "btn small", type: "button", disabled: item.read }, item.read ? "읽음" : "읽음 표시");
          read.onclick = async () => {
            read.disabled = true;
            try { await markInboxRead(item.id); }
            catch (err) { read.disabled = false; toast(err.message, "error"); }
          };
          const link = h("a", { class: "btn small", href: item.url }, "내용 확인");
          let opening = false;
          link.onclick = async event => {
            event.preventDefault();
            if (opening) return;
            opening = true;
            const path = location.hash, openingVersion = panelVersion;
            try {
              if (!item.read) await markInboxRead(item.id);
              if (location.hash === path && panelVersion === openingVersion && !panel.hidden) { close(); location.hash = item.url.split("#")[1]; }
            } catch (err) { toast(err.message, "error"); }
            finally { opening = false; }
          };
          return h("article", { class: `inbox-preview ${item.read ? "is-read" : "is-unread"}` },
            h("div", { class: "inbox-item-heading" }, h("h3", {}, item.title),
              h("span", { class: "inbox-read-state" }, item.read ? "읽음" : "읽지 않음")), h("p", {}, item.body),
            h("small", {}, `알림 시각 ${item.arrived_at ? item.arrived_at.slice(0, 16).replace("T", " ") + " (한국시간)" : item.arrived_on || item.created_on}`), h("div", { class: "actions" },
              link, read));
        }),
        !data.items.length ? h("p", {}, "새 알림이 없습니다.") : null,
        h("div", { class: "actions" }, h("a", { class: "btn small", href: "#/inbox", onclick: () => close() }, "알림 전체 보기"), readAll, refreshButton));
    } catch (err) {
      mount(panel, h("p", { class: "error-box" }, "알림을 불러오지 못했습니다."),
        h("button", { class: "btn small", type: "button", onclick: refresh }, "다시 시도"),
        h("button", { class: "btn small", type: "button", onclick: () => close(true) }, "닫기"));
    } finally { pending = false; if (refreshAgain) { refreshAgain = false; refresh(); } }
  }
  button.onclick = () => {
    if (!panel.hidden) { close(); return; }
    document.getElementById("nav").classList.remove("open");
    document.getElementById("menu-btn")?.setAttribute("aria-expanded", "false");
    panel.hidden = false;
    button.setAttribute("aria-expanded", "true");
    refresh();
  };
  wrap.addEventListener("keydown", e => { if (e.key === "Escape" && !panel.hidden) { e.preventDefault(); close(true); } });
  document.addEventListener("click", e => { if (!wrap.contains(e.target)) close(); });
  window.addEventListener("hashchange", () => close());
  window.addEventListener("inbox-count", e => setCount(e.detail));
  window.addEventListener("inbox-changed", refresh);
  // Refresh on a real return to the app, not a timer that keeps Neon awake.
  window.addEventListener("focus", () => { if (!document.hidden) refresh(); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  refresh();
  return wrap;
}
