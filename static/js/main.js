import { inboxBell } from "./components/inbox-bell.js";
import { navIcon } from "./components/nav-icon.js";
import { personalAlerts, pushButton } from "./push.js";
import { initializePwa, installButton, isStandalone } from "./pwa.js";
// 앱 시작점: 로그인 확인 → 메뉴 구성 → 라우터 시작
import { ApiError, get, post, setCsrf } from "./api.js";
import { go, navItems, resolve, route } from "./router.js";
import { can, feature, state } from "./state.js";
import { h, mount } from "./ui.js";
import * as admin from "./views/admin.js";
import * as login from "./views/login.js";
import * as myBookings from "./views/my-bookings.js";
import * as profBookings from "./views/prof-bookings.js";
import * as profSlots from "./views/prof-slots.js";
import * as staffInsights from "./views/staff-insights.js";
import * as studentBooking from "./views/student-booking.js";
import * as editor from "./views/survey-editor.js";
import * as suggestions from "./views/suggestions.js";
import * as surveys from "./views/surveys.js";
import * as support from "./views/support.js";
import * as inbox from "./views/inbox.js";

function home(root) {
  if (can("slot:manage")) return go("/slots");
  if (can("booking:self")) return go("/booking");
  mount(root, h("p", {}, "환영합니다."));
}

function registerRoutes() {
  route("/", null, home);
  // 학생
  route("/booking", "booking:self", studentBooking.render, "상담 예약");
  route("/my-bookings", "booking:self", myBookings.render, "내 예약");
  route("/personal", "booking:manage", personalAlerts);
  if (["professor", "admin"].includes(state.me.role)) route("/inbox", "booking:manage", inbox.render, "내 알림");
  route("/inbox/:id", "booking:manage", inbox.renderTarget);
  route("/bookings/today", "booking:manage", profBookings.todayBookings);
  route("/staff/today", "booking:manage", () => go("/bookings"));
  // 교수자·관리자
  route("/slots", "slot:manage", profSlots.render, "시간표");
  route("/slots/new", "slot:manage", profSlots.renderRegistration);
  route("/bookings", "booking:manage", profBookings.render, "예약 관리");
  route("/staff/insights", "booking:manage", staffInsights.render, "상담 기록·통계");
  if (feature("surveys")) {
    route("/surveys", null, surveys.renderList, "설문");
    // Restart in the public-only entry point, without reading the login session.
    route("/surveys/public/:token", null, (_root, { token }) => {
      if (/^[A-Za-z0-9_-]{32}$/.test(token)) location.reload();
      else go("/surveys");
    });
    route("/surveys/take/:id", "survey:respond", surveys.renderTake);
    route("/surveys/edit/:id", "survey:manage", editor.render);
    route("/surveys/results/:id", "survey:results", surveys.renderResults);
  }
  if (feature("suggestions")) route("/suggestions", null, suggestions.render, can("suggestion:read") ? "건의함" : "익명 건의");
  route("/help", "slot:view", support.renderHome);
  route("/help/new", "slot:view", support.renderNew);
  route("/help/mine", "slot:view", (root) => support.renderList(root));
  route("/help/tickets/:id", "slot:view", support.renderDetail);
  route("/help/inbox", "support:manage", (root) => support.renderList(root, true));
  route("/help/inbox/:id", "support:manage", (root, params) => support.renderDetail(root, params, true));
  // 관리자
  route("/admin/users", "user:manage", admin.renderUsers, "계정·권한");
  route("/admin/settings", "settings:manage", admin.renderSettings, "운영 설정");
  route("/admin/audit", "audit:view", admin.renderAudit, "작업 이력");
}

function closeMobileMenu(restoreFocus = false) {
  const nav = document.getElementById("nav");
  nav?.classList.remove("open");
  nav?.querySelectorAll(".nav-group").forEach(group => { group.open = matchMedia("(max-width: 720px)").matches; });
  const button = document.getElementById("menu-btn");
  button?.setAttribute("aria-expanded", "false");
  if (restoreFocus) button?.focus({ preventScroll: true });
}

function renderMobileTabs() {
  const tabs = document.getElementById("mobile-tabs");
  const items = can("slot:manage")
    ? [{ pattern: "/slots", navLabel: "시간표" }, { pattern: "/bookings", navLabel: "예약 관리" },
       { pattern: "/inbox", navLabel: "내 알림" }]
    : ["/booking", "/my-bookings", "/surveys"].map(path => navItems().find(r => r.pattern === path)).filter(Boolean);
  mount(tabs,
    ...items.map((r) => h("a", { href: `#${r.pattern}` },
      navIcon(r.pattern), h("span", {}, r.navLabel))),
    h("button", { id: "menu-btn", type: "button", "aria-controls": "nav", "aria-expanded": "false",
      "aria-label": "더보기 메뉴", onclick: (event) => {
        const nav = document.getElementById("nav");
        const open = nav.classList.toggle("open");
        event.currentTarget.setAttribute("aria-expanded", String(open));
        if (open) [...nav.querySelectorAll("a, button")].find(el => el.getClientRects().length > 0)?.focus({ preventScroll: true });
      } },
    h("span", { class: "mobile-tab-icon", "aria-hidden": "true" }, "☰"), h("span", {}, "더보기")));
  // Keep the sheet attached to the real tab-bar height, including safe areas.
  if (!tabs._heightObserver) {
    tabs._heightObserver = new ResizeObserver(() => document.documentElement.style.setProperty("--mobile-tabs-height", `${tabs.getBoundingClientRect().height}px`));
    tabs._heightObserver.observe(tabs);
  }
  const active = location.hash;
  tabs.querySelectorAll("a").forEach((a) => {
    const current = a.getAttribute("href") === active || (a.getAttribute("href") === "#/slots" && active === "#/slots/new") ||
      (a.getAttribute("href") === "#/bookings" && active === "#/bookings/today");
    a.classList.toggle("active", current);
    if (current) a.setAttribute("aria-current", "page");
  });
}

function renderChrome() {
  const nav = document.getElementById("nav");
  const items = navItems();
  const link = (r) => h("a", { class: (["/slots", "/bookings", "/inbox", "/booking", "/my-bookings", ...(!can("slot:manage") ? ["/surveys"] : [])].includes(r.pattern) ? "bottom-tab-duplicate" : ""), href: `#${r.pattern}` }, navIcon(r.pattern), h("span", {}, r.navLabel));
  if (can("slot:manage")) {
    const groups = [
      ["예약 관리", ["/slots", "/bookings"]],
      ["상담 기록·알림", ["/staff/insights", "/inbox"]],
      ["설문·건의", ["/surveys", "/suggestions"]],
      ["관리", ["/admin/users", "/admin/settings", "/admin/audit"]],
    ];
    mount(nav, groups.map(([label, paths]) => {
      const entries = paths.map(path => items.find(r => r.pattern === path)).filter(Boolean);
      if (!entries.length) return null;
      if (entries.length === 1) return link(entries[0]);
      return h("details", { class: "nav-group", open: matchMedia("(max-width: 720px)").matches },
        h("summary", {}, label), h("div", { class: "nav-group-links" }, entries.map(link)));
    }));
  } else mount(nav, items.map(link));
  nav.addEventListener("toggle", event => {
    if (matchMedia("(max-width: 720px)").matches || !event.target.matches(".nav-group[open]")) return;
    nav.querySelectorAll(".nav-group").forEach(group => { if (group !== event.target) group.open = matchMedia("(max-width: 720px)").matches; });
  }, true);
  document.addEventListener("click", event => {
    if (!nav.contains(event.target)) nav.querySelectorAll(".nav-group").forEach(group => { group.open = matchMedia("(max-width: 720px)").matches; });
  });
  document.addEventListener("click", event => {
    if (!nav.contains(event.target) && !event.target.closest("#menu-btn") && !event.target.closest(".userbox")) closeMobileMenu();
  });
  nav.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    if (matchMedia("(max-width: 720px)").matches) { closeMobileMenu(true); return; }
    const group = event.target.closest(".nav-group");
    if (group) { group.open = matchMedia("(max-width: 720px)").matches; group.querySelector("summary").focus(); }
  });
  const help = support.helpLink("mobile-help-link");
  help.prepend(navIcon("/help"));
  nav.append(help);
  const personal = pushButton("mobile-help-link");
  if (personal) { personal.prepend(navIcon("/personal")); nav.append(personal); }
  const install = installButton("btn mobile-help-link");
  if (install) nav.append(install);
  const roleLabel = { student: "학생", professor: "교수자", admin: "관리자" }[state.me.role];
  nav.append(h("div", { class: "mobile-menu-account" },
    h("span", {}, `${state.me.name} · ${roleLabel}`),
    h("button", { class: "btn small", onclick: async () => { await post("/auth/logout"); location.hash = ""; location.reload(); } }, "로그아웃")));
  mount(document.getElementById("userbox"),
    support.helpLink("btn small desktop-help-link"),
      pushButton('desktop-help-link'),
    h("span", { class: "who" }, `${state.me.name} · ${roleLabel}`),
    h("button", { class: "btn small", onclick: async () => { await post("/auth/logout"); location.hash = ""; location.reload(); } }, "로그아웃"));
  if (["professor", "admin"].includes(state.me.role)) document.querySelector(".topbar").append(inboxBell());
  nav.addEventListener("click", (event) => {
    if (!event.target.closest("a")) return;
    nav.querySelectorAll(".nav-group").forEach(group => { group.open = matchMedia("(max-width: 720px)").matches; });
    nav.classList.remove("open");
    document.getElementById("menu-btn").setAttribute("aria-expanded", "false");
  });
  matchMedia("(max-width: 720px)").addEventListener("change", event => {
    nav.querySelectorAll(".nav-group").forEach(group => { group.open = event.matches; });
  });
  renderMobileTabs();
  support.rememberSource();
  support.refreshCounts();
  window.addEventListener("hashchange", () => { nav.classList.remove("open"); renderMobileTabs(); support.rememberSource(); support.refreshCounts(); });
  window.addEventListener("focus", support.refreshCounts);
}

async function start() {
  const view = document.getElementById("view");
  const publicSurvey = location.hash.match(/^#\/surveys\/public\/([A-Za-z0-9_-]{32})$/);
  if (publicSurvey) {
    document.getElementById("mobile-tabs").hidden = true;
    await surveys.renderPublic(view, publicSurvey[1]);
    window.addEventListener("hashchange", () => location.reload());
    return;
  }
  try {
    state.me = await get("/api/me");
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      document.getElementById("mobile-tabs").hidden = true;
      await login.render(view);
      return;
    }
    mount(view, h("p", { class: "error-box" }, e.message));
    return;
  }
  setCsrf(state.me.csrf_token);
  registerRoutes();
  renderChrome();
  window.addEventListener("hashchange", resolve);
  await resolve();
}

document.querySelector(".skip-link")?.addEventListener("click", (event) => {
  event.preventDefault();
  document.getElementById("view").focus();
});

initializePwa();
start();
