import { get, put } from "../api.js";
import { h, mount, toast } from "../ui.js";

export async function render(root) {
  const list = h("section", { "aria-label": "내 알림 목록" });
  const count = h("p", { "aria-live": "polite" });
  const refresh = h("button", { class: "btn", type: "button" }, "알림 새로고침");
  async function draw() {
    refresh.disabled = true;
    try {
      const data = await get("/api/inbox");
      window.dispatchEvent(new CustomEvent("inbox-count", { detail: data.unread }));
      count.textContent = `읽지 않은 알림 ${data.unread}건`;
      mount(list, ...data.items.map(item => {
        const read = h("button", { class: "btn small", type: "button", disabled: item.read }, item.read ? "읽음" : "읽음 표시");
        read.onclick = async () => {
          read.disabled = true;
          try { await put(`/api/inbox/${item.id}/read`); await draw(); }
          catch (e) { read.disabled = false; toast(e.message, "error"); }
        };
        return h("article", { class: "panel" }, h("h2", {}, item.title),
          h("p", {}, item.body), h("small", { class: "muted" }, item.created_on),
          h("div", { class: "actions" }, h("a", { class: "btn small", href: item.url }, "내용 확인"), read));
      }));
      if (!data.items.length) mount(list, h("p", { class: "empty" }, "새 알림이 없습니다. 기능 적용 후 접수된 알림부터 표시됩니다."));
    } catch (e) { mount(list, h("p", { class: "error-box" }, e.message)); }
    finally { refresh.disabled = false; }
  }
  refresh.onclick = draw;
  mount(root, h("h1", {}, "내 알림"),
    h("p", { class: "hint" }, "앱 안 알림은 휴대폰 푸시 허용 여부와 관계없이 보관됩니다. 최근 100건을 표시하며 화면을 열거나 새로고침할 때 갱신합니다."),
    h("a", { class: "btn small", href: "#/personal" }, "휴대폰 알림 설정"), count, refresh, list);
  await draw();
}
