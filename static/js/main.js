import { navIcon } from "./components/nav-icon.js";
import { pushButton } from "./push.js";
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

function home(root) {
  if (can("slot:manage")) return go(isStandalone() ? "/bookings" : "/slots");
  if (can("booking:self")) return go("/booking");
  mount(root, h("p", {}, "환영합니다."));
}

function registerRoutes() {
  route("/", null, home);
  // 학생
  route("/booking", "booking:self", studentBooking.render, "상담 예약");
  route("/my-bookings", "booking:self", myBookings.render, "내 예약");
  route("/staff/today", "booking:manage", () => go("/bookings"));
  // 교수자·관리자
  route("/slots", "slot:manage", profSlots.render, "상담 시간");
  route("/bookings", "booking:manage", profBookings.render, "예약 관리");
  route("/staff/insights", "booking:manage", staffInsights.render, "상담 정보");
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

function renderMobileTabs() {
  const tabs = document.getElementById("mobile-tabs");
  const items = isStandalone() && can("booking:manage")
    ? [{ pattern: "/slots", navLabel: "상담 시간" }, { pattern: "/bookings", navLabel: "예약 관리" },
       { pattern: "/staff/insights", navLabel: "상담 정보" }]
    : navItems().slice(0, 3);
  mount(tabs,
    ...items.map((r) => h("a", { href: `#${r.pattern}` },
      navIcon(r.pattern),
      h("span", {}, navIcon(r.pattern), h("span", {}, r.navLabel)))),
    h("button", { type: "button", onclick: () => {
      const menu = document.getElementById("menu-btn");
      menu.click();
      if (menu.getAttribute("aria-expanded") === "true") menu.focus();
    }, "aria-label": "더보기 메뉴" },
    h("span", { class: "mobile-tab-icon", "aria-hidden": "true" }, "☰"), h("span", {}, "더보기")));
  const active = location.hash;
  tabs.querySelectorAll("a").forEach((a) => {
    const current = a.getAttribute("href") === active;
    a.classList.toggle("active", current);
    if (current) a.setAttribute("aria-current", "page");
  });
}

function renderChrome() {
  const nav = document.getElementById("nav");
  mount(nav, navItems().map((r) => h("a", { href: `#${r.pattern}`, onclick: () => nav.classList.remove("open") }, navIcon(r.pattern), h("span", {}, r.navLabel))));
  const mobileHelp = support.helpLink("mobile-help-link");
  mobileHelp.onclick = () => { nav.classList.remove("open"); document.getElementById("menu-btn").setAttribute("aria-expanded", "false"); };
  nav.append(mobileHelp);
  const install = installButton("btn mobile-help-link");
  if (install) {
    install.addEventListener("click", () => {
      nav.classList.remove("open");
      document.getElementById("menu-btn").setAttribute("aria-expanded", "false");
    });
    nav.append(install);
  }
  const roleLabel = { student: "학생", professor: "교수자", admin: "관리자" }[state.me.role];
  mount(document.getElementById("userbox"),
    support.helpLink("btn small desktop-help-link"),
      pushButton(),
    h("span", { class: "who" }, `${state.me.name} · ${roleLabel}`),
    h("button", { class: "btn small", onclick: async () => { await post("/auth/logout"); location.hash = ""; location.reload(); } }, "로그아웃"));
  const menu = document.getElementById("menu-btn");
  menu.onclick = () => { const o = nav.classList.toggle("open"); menu.setAttribute("aria-expanded", String(o)); };
  renderMobileTabs();
  support.rememberSource();
  support.refreshCounts();
  window.addEventListener("hashchange", () => { renderMobileTabs(); support.rememberSource(); support.refreshCounts(); });
  window.addEventListener("focus", support.refreshCounts);
}

async function start() {
  const view = document.getElementById("view");
  const publicSurvey = location.hash.match(/^#\/surveys\/public\/([A-Za-z0-9_-]{32})$/);
  if (publicSurvey) {
    document.getElementById("menu-btn").hidden = true;
    document.getElementById("mobile-tabs").hidden = true;
    await surveys.renderPublic(view, publicSurvey[1]);
    window.addEventListener("hashchange", () => location.reload());
    return;
  }
  try {
    state.me = await get("/api/me");
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      document.getElementById("menu-btn").hidden = true;
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

initializePwa();
start();
