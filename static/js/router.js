// 해시 라우터. 각 라우트는 필요한 권한을 선언하고, 권한 없으면 홈으로 보낸다(표시 목적).
import { can } from "./state.js";
import { h, mount } from "./ui.js";

const routes = [];
let resolution = 0;

export function route(pattern, perm, render, navLabel) {
  const keys = [];
  const re = new RegExp("^" + pattern.replace(/:(\w+)/g, (_, k) => { keys.push(k); return "([^/]+)"; }) + "$");
  routes.push({ pattern, re, keys, perm, render, navLabel });
}

export function navItems() {
  return routes.filter((r) => r.navLabel && (!r.perm || can(r.perm)));
}

export function go(path) { location.hash = "#" + path; }

export async function resolve() {
  const path = location.hash.replace(/^#/, "") || "/";
  const version = ++resolution;
  // Give each navigation its own mount target. A late response from the previous
  // route may finish rendering, but must never replace the current screen.
  const previousView = document.getElementById("view");
  const view = previousView.cloneNode(false);
  previousView.replaceWith(view);
  document.body.dataset.ready = ""; // 렌더링 완료 표시 (접근성·E2E 대기용)
  for (const r of routes) {
    const m = path.match(r.re);
    if (!m) continue;
    if (r.perm && !can(r.perm)) {
      mount(view, h("p", { class: "empty" }, "접근 권한이 없는 화면입니다."));
      return;
    }
    const params = Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])]));
    document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${r.pattern}`));
    mount(view, h("p", { class: "loading" }, "불러오는 중…"));
    try {
      await r.render(view, params);
    } catch (e) {
      mount(view, h("p", { class: "error-box" }, e.message || "오류가 발생했습니다"),
        h("button", { class: "btn", onclick: () => resolve() }, "다시 시도"));
    }
    if (version !== resolution || !view.isConnected) return;
    view.focus({ preventScroll: true });
    if ((location.hash.replace(/^#/, "") || "/") === path) document.body.dataset.ready = path;
    return;
  }
  go("/");
}
