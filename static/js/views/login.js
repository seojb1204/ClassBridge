// 로그인 화면. 개발 환경에서만 이메일 개발용 로그인이 표시된다.
import { get, post } from "../api.js";
import { busy, errorToast, field, h, mount } from "../ui.js";

export async function render(root) {
  const cfg = await get("/api/auth/config");
  const parts = [h("h1", {}, "ClassBridge"), h("p", { class: "muted" }, "교수자와 학생을 위한 상담 예약")];
  if (cfg.google) parts.push(h("a", { class: "btn primary big", href: "/auth/google/login" }, "Google 계정으로 로그인"));
  if (cfg.notice) {
    parts.push(h("p", { class: "muted" }, "상담 예약에 필요한 계정 정보와 예약 정보를 처리합니다."),
      h("p", {}, h("a", { href: cfg.notice.url, target: "_blank", rel: "noopener" }, "개인정보처리방침")));
    parts.push(h("p", { class: "muted" }, "문의: ", h("a", { href: `mailto:${cfg.notice.support_email}` }, cfg.notice.support_email)));
  }
  if (cfg.dev_login) {
    const email = h("input", { type: "email", required: true, placeholder: "student1@test.ac.kr", name: "email" });
    const btn = h("button", { class: "btn", type: "submit" }, "개발용 로그인");
    const form = h("form", { class: "dev-login" }, h("p", { class: "warn" }, "개발 환경 전용 — 운영에서는 비활성화됩니다"),
      field("이메일", email), btn);
    form.addEventListener("submit", busy(btn, async (e) => {
      e.preventDefault();
      try { await post("/auth/dev/login", { email: email.value }); location.hash = "#/"; location.reload(); }
      catch (err) { errorToast(err); }
    }));
    parts.push(form);
  }
  if (!cfg.google && !cfg.dev_login) parts.push(h("p", { class: "error-box" }, "로그인 방식이 설정되지 않았습니다. 관리자에게 문의하세요."));
  mount(root, h("div", { class: "login-box panel" }, parts));
}
