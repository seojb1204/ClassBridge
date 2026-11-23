import { watchRefresh } from "../live-refresh.js";
import { inboxRow } from "../components/inbox-row.js";
import { get } from "../api.js";
import { h, mount, toast } from "../ui.js";

import { inboxVersion, markInboxRead, publishInboxCount } from "../inbox-state.js";
let renderVersion = 0;

export async function render(root) {
  const renderId = ++renderVersion;
  const isCurrent = () => renderId === renderVersion && location.hash === "#/inbox";
  const list = h("section", { "aria-label": "내 알림 목록" });
  const count = h("p", { "aria-live": "polite" });
  const refresh = h("button", { class: "btn", type: "button", hidden: true }, "다시 시도");
  const more = h("button", { class: "btn inbox-more", type: "button", hidden: true }, "이전 알림 더 보기");
  const all = h("button", { class: "btn primary", type: "button", "aria-pressed": "true" }, "전체 알림");
  const unread = h("button", { class: "btn", type: "button", "aria-pressed": "false" }, "미읽음만");
  const readAll = h("button", { class: "btn", type: "button", disabled: true }, "모두 읽음 처리");
  let items = [], cursor = null, unreadOnly = false, pending = false, refreshAgain = false;
  function paint() {
    mount(list, ...items.map(item => {
      const link = inboxRow(item);
      let opening = false;
      link.onclick = async event => {
        event.preventDefault();
        if (opening) return;
        opening = true;
        try {
          if (!item.read) await markInboxRead(item.id);
          if (isCurrent()) location.hash = item.url.split("#")[1];
        } catch (e) { toast(e.message, "error"); }
        finally { opening = false; }
      };
      link.classList.add("panel", "inbox-item");
      link.dataset.notificationId = item.id;
      return link;
    }));
    if (!items.length) mount(list, h("p", { class: "empty" }, unreadOnly ? "읽지 않은 알림이 없습니다." : "새 알림이 없습니다. 기능 적용 후 접수된 알림부터 표시됩니다."));
  }
  async function draw(reset = true, automatic = false) {
    if (!isCurrent()) return;
    if (pending) { refreshAgain = true; return; }
    pending = true;
    const version = inboxVersion();
    refresh.disabled = more.disabled = all.disabled = unread.disabled = true;
    try {
      const q = new URLSearchParams({ limit: 50, unread_only: unreadOnly });
      if (!reset && cursor !== null) q.set("before_id", cursor);
      const data = await get(`/api/inbox?${q}`);
      if (!isCurrent()) return;
      if (version !== inboxVersion()) { refreshAgain = true; return; }
      publishInboxCount(data.unread);
      readAll.disabled = !data.unread;
      count.textContent = `읽지 않은 알림 ${data.unread}건`;
      refresh.hidden = true;
      const anchor = automatic ? [...list.querySelectorAll('[data-notification-id]')].find(el => el.getBoundingClientRect().bottom > (document.querySelector('.topbar')?.getBoundingClientRect().bottom || 0)) : null;
      const anchorId = anchor?.dataset.notificationId, anchorY = anchor?.getBoundingClientRect().top;
      const previousScroll = window.scrollY;
      // Keep older loaded pages during background refresh; explicit filters reset them.
      if (automatic) {
        const freshIds = new Set(data.items.map(item => item.id));
        items = [...data.items, ...(data.has_more ? items.filter(item => !freshIds.has(item.id) && item.id < data.items.at(-1)?.id) : [])];
      } else items = reset ? data.items : [...items, ...data.items.filter(x => !items.some(old => old.id === x.id))];
      if (!automatic || cursor === null) { cursor = data.next_before_id ?? null; more.hidden = !data.has_more; }
      paint();
      if (automatic && previousScroll > 0) {
        const nextAnchor = [...list.querySelectorAll('[data-notification-id]')].find(el => el.dataset.notificationId === anchorId);
        window.scrollTo({top: nextAnchor ? previousScroll + nextAnchor.getBoundingClientRect().top - anchorY : previousScroll, behavior: 'instant'});
      }
    } catch (e) { refresh.hidden = false; toast(e.message, "error"); }
    finally { pending = false; refresh.disabled = more.disabled = all.disabled = unread.disabled = false;
      if (refreshAgain) { refreshAgain = false; draw(true); }
    }
  }
  function filter(value) {
    unreadOnly = value;
    all.className = value ? "btn" : "btn primary";
    unread.className = value ? "btn primary" : "btn";
    all.setAttribute("aria-pressed", String(!value)); unread.setAttribute("aria-pressed", String(value));
    draw(true);
  }
  readAll.onclick = async () => {
    readAll.disabled = true;
    try { await markInboxRead(null); }
    catch (e) { readAll.disabled = false; toast(e.message, "error"); }
  };
  const update = () => { if (isCurrent() && !document.hidden) draw(true); };
  window.addEventListener("inbox-changed", update);


  const cleanup = () => {
    window.removeEventListener("inbox-changed", update);
    window.removeEventListener("focus", update);
    document.removeEventListener("visibilitychange", update);
    window.removeEventListener("hashchange", cleanup);
  };
  window.addEventListener("hashchange", cleanup);
  all.onclick = () => filter(false); unread.onclick = () => filter(true);
  refresh.onclick = () => draw(true); more.onclick = () => draw(false);
  readAll.classList.add("inbox-read-all");
  mount(root, h("h1", {}, "내 알림"),
    count, h("div", { class: "toolbar inbox-controls" }, all, unread, readAll), refresh, list, more,
    h("details", {class: "help-details"}, h("summary", {}, "알림 시각·갱신 안내"),
      h("p", {}, "최신순 · 한국시간. 이 화면을 보는 동안 60초마다, 화면으로 돌아올 때 갱신합니다. 알림 시각은 앱에서 확인 가능해진 시각이며 휴대폰 수신 시각과 다를 수 있습니다.")));
  await draw();
  if (isCurrent()) watchRefresh(root, () => draw(true, true), () => { refresh.hidden = false; }, 60000);
}


export async function renderTarget(root, { id }) {
  const data = await get(`/api/inbox/${encodeURIComponent(id)}/target`);
  if (!root.isConnected) return;
  if (data.type === "suggestion") { location.hash = "#/suggestions"; return; }
  const back = h("a", { class: "btn", href: "#/inbox" }, "알림 목록으로");
  if (data.type === "booking" && data.booking) {
    const { openNotification } = await import("./prof-bookings.js");
    if (root.isConnected) await openNotification(root, data.booking, data.notification);
    return;
  }
  mount(root, h("h1", {}, data.notification.title),
    h("section", { class: "panel notification-target", tabindex: -1 },
      h("p", {}, data.unavailable ? "이 알림의 예약을 찾을 수 없습니다. 삭제되었거나 이전 알림에 연결 정보가 없습니다." : data.notification.body)),
    data.type === "booking" ? h("a", { class: "btn", href: "#/bookings" }, "예약 관리로") : null, back);
  const target = root.querySelector(".notification-target");
  target?.focus();
  setTimeout(() => target?.classList.remove("notification-target"), 2800);
}
