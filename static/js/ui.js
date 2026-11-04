// 공통 UI. 모든 텍스트는 textContent로 넣는다 (innerHTML 사용 금지 → XSS 방지).

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(el.dataset, v);
    else if (k in el && typeof v !== "string") el[k] = v;
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function mount(root, ...nodes) {
  root.replaceChildren(...nodes.flat());
}

export function toast(message, kind = "info") {
  const box = document.getElementById("toasts");
  const t = h("div", { class: `toast toast-${kind}`, role: kind === "error" ? "alert" : "status" }, message);
  box.append(t);
  setTimeout(() => t.remove(), kind === "error" ? 6000 : 3500);
}

export function errorToast(e) { toast(e?.message || String(e), "error"); }

// window.confirm 대신 자체 모달 (브라우저 차단 대화상자 회피)
export function modal(title, body, actions) {
  return new Promise((resolve) => {
    const root = document.getElementById("modal-root");
    const returnFocus = document.activeElement;
    let pending = false;
    let closed = false;
    let box;
    const close = (value) => {
      if (closed) return;
      closed = true;
      document.removeEventListener("keydown", handleKeys);
      root.replaceChildren();
      if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
      resolve(value);
    };
    const focusables = () => [...box.querySelectorAll(
      'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )].filter((el) => el.getClientRects().length > 0);
    const handleKeys = (event) => {
      if (closed) return;
      if (event.key === "Escape") {
        event.preventDefault();
        if (!pending) close(null);
      }
      if (event.key !== "Tab") return;
      const els = focusables();
      if (!els.length) { event.preventDefault(); box.focus(); return; }
      const first = els[0], last = els[els.length - 1];
      if (event.shiftKey && (document.activeElement === first || !box.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !box.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    };
    box = h("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-label": title,
      tabindex: -1 },
      h("h2", {}, title),
      h("div", { class: "modal-body" }, body),
      h("div", { class: "modal-actions" },
        ...actions.map((action) => h("button", {
          class: action.primary ? "btn primary" : action.danger ? "btn danger" : "btn",
          onclick: async () => {
            if (pending || closed) return;
            if (!action.handler) { close(action.value); return; }
            pending = true;
            const buttons = box.querySelectorAll(".modal-actions button");
            buttons.forEach((btn) => { btn.disabled = true; });
            try {
              const result = await action.handler();
              if (result !== false) { close(result ?? action.value); return; }
            } catch (e) {
              errorToast(e);
            } finally {
              pending = false;
              if (!closed) buttons.forEach((btn) => { btn.disabled = false; });
            }
          },
        }, action.label))));
    const backdrop = h("div", { class: "backdrop", onclick: (e) => {
      if (e.target === backdrop && !pending) close(null);
    } }, box);
    root.replaceChildren(backdrop);
    document.addEventListener("keydown", handleKeys);
    (focusables()[0] || box).focus({ preventScroll: true });
  });
}

export async function confirmAction(title, message, label = "확인", danger = false) {
  const r = await modal(title, h("p", {}, message), [
    { label: "취소", value: false }, { label, value: true, primary: !danger, danger },
  ]);
  return r === true;
}

export async function promptText(title, label, { required = false, multiline = false, value = "" } = {}) {
  const input = multiline ? h("textarea", { rows: 5, maxlength: 10000 }) : h("input", { type: "text", maxlength: 500 });
  input.value = value;
  const r = await modal(title, h("label", { class: "field" }, label, input), [
    { label: "취소", value: null },
    { label: "확인", primary: true, handler: () => {
      if (required && !input.value.trim()) { input.focus(); toast("내용을 입력하세요", "error"); return false; }
      return input.value;
    } },
  ]);
  return r;
}

export function field(label, input, hint) {
  return h("label", { class: "field" }, h("span", { class: "label" }, label), input,
    hint ? h("small", { class: "hint" }, hint) : null);
}

export function select(options, value) {
  const s = h("select", {});
  for (const [v, text] of options) s.append(h("option", { value: v }, text));
  if (value !== undefined) s.value = value;
  return s;
}

export function badge(text, kind = "") { return h("span", { class: `badge ${kind}` }, text); }

export function empty(text) { return h("p", { class: "empty" }, text); }

export function busy(btn, fn) {
  // 중복 클릭 방지: 처리 중 버튼 비활성화
  return async (...args) => {
    if (btn.disabled) return;
    btn.disabled = true;
    try { return await fn(...args); } finally { btn.disabled = false; }
  };
}

export const STATUS_LABEL = {
  booked: "예약됨", cancelled: "취소됨", completed: "완료", no_show: "미참석",
  draft: "초안", published: "게시 중", closed: "종료", new: "새 건의", reviewed: "확인함", archived: "보관",
};
