import { get, put } from "../api.js";
import { h, mount, toast } from "../ui.js";

export async function render(root) {
  const list = h("section", { "aria-label": "내 알림 목록" });
  const count = h("p", { "aria-live": "polite" });
  const refresh = h("button", { class: "btn", type: "button" }, "알림 새로고침");
  const more = h("button", { class: "btn inbox-more", type: "button", hidden: true }, "이전 알림 더 보기");
  const all = h("button", { class: "btn primary", type: "button", "aria-pressed": "true" }, "전체 알림");
  const unread = h("button", { class: "btn", type: "button", "aria-pressed": "false" }, "미읽음만");
  let items = [], cursor = null, unreadOnly = false, pending = false;
  function paint() {
    mount(list, ...items.map(item => {
      const read = h("button", { class: "btn small", type: "button", disabled: item.read }, item.read ? "읽음" : "읽음 표시");
      read.onclick = async () => {
        read.disabled = true;
        try { await put(`/api/inbox/${item.id}/read`); await draw(true); }
        catch (e) { read.disabled = false; toast(e.message, "error"); }
      };
      return h("article", { class: "panel", dataset: { notificationId: item.id } }, h("h2", {}, item.title),
        h("p", {}, item.body), h("small", { class: "muted" }, `알림 시각 ${item.arrived_at ? item.arrived_at.slice(0, 16).replace("T", " ") + " (한국시간)" : item.arrived_on || item.created_on}`),
        h("div", { class: "actions" }, h("a", { class: "btn small", href: item.url }, "내용 확인"), read));
    }));
    if (!items.length) mount(list, h("p", { class: "empty" }, unreadOnly ? "읽지 않은 알림이 없습니다." : "새 알림이 없습니다. 기능 적용 후 접수된 알림부터 표시됩니다."));
  }
  async function draw(reset = true) {
    if (pending) return;
    pending = true;
    refresh.disabled = more.disabled = all.disabled = unread.disabled = true;
    try {
      const q = new URLSearchParams({ limit: 50, unread_only: unreadOnly });
      if (!reset && cursor !== null) q.set("before_id", cursor);
      const data = await get(`/api/inbox?${q}`);
      window.dispatchEvent(new CustomEvent("inbox-count", { detail: data.unread }));
      count.textContent = `읽지 않은 알림 ${data.unread}건`;
      items = reset ? data.items : [...items, ...data.items.filter(x => !items.some(old => old.id === x.id))];
      cursor = data.next_before_id ?? null;
      more.hidden = !data.has_more;
      paint();
    } catch (e) { toast(e.message, "error"); }
    finally { pending = false; refresh.disabled = more.disabled = all.disabled = unread.disabled = false; }
  }
  function filter(value) {
    unreadOnly = value;
    all.className = value ? "btn" : "btn primary";
    unread.className = value ? "btn primary" : "btn";
    all.setAttribute("aria-pressed", String(!value)); unread.setAttribute("aria-pressed", String(value));
    draw(true);
  }
  all.onclick = () => filter(false); unread.onclick = () => filter(true);
  refresh.onclick = () => draw(true); more.onclick = () => draw(false);
  mount(root, h("h1", {}, "내 알림"),
    h("p", { class: "hint" }, "알림 시각 최신순으로 표시합니다. 새 건의는 접수 즉시 알림을 생성합니다. 화면을 열거나 새로고침할 때 갱신합니다. 알림 시각은 앱에서 확인 가능해진 시각이며 실제 휴대폰 수신 시각이 아닙니다. 이전 지연 알림은 당시 예정 시각을 표시하며 제출 시각을 뜻하지 않습니다."),
    h("a", { class: "btn small", href: "#/personal" }, "휴대폰 알림 설정"), count,
    h("div", { class: "toolbar" }, all, unread, refresh), list, more);
  await draw();
}
