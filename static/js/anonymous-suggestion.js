import { busy, errorToast, field, h, mount, select, toast } from "./ui.js";
import { CATS } from "./suggestion-categories.js";

async function submitForm(root) {
  const cat = select(CATS, "lecture");
  const content = h("textarea", { rows: 6, maxlength: 2000, required: true, placeholder: "자유롭게 의견을 남겨 주세요." });
  const visibility = select([["private", "교수자·관리자에게만 전달"], ["public", "로그인한 이용자에게 공개"]], "private");
  const counter = h("small", { class: "hint" }, "0 / 2000");
  content.addEventListener("input", () => { counter.textContent = `${content.value.length} / 2000`; });
  const btn = h("button", { class: "btn primary", type: "submit" }, "익명으로 제출");
  const form = h("form", { class: "panel" },
    h("p", { class: "muted" }, "이 건의는 Google 계정과 연결되지 않습니다."),
    h("a", { href: "/privacy", target: "_blank", rel: "noopener" }, "개인정보처리방침"),
    field("공개 범위", visibility),
    h("p", { class: "hint" }, "공개 선택 시 모든 로그인 이용자가 내용과 교수자 답변을 봅니다. 비공개 건의는 교수자 검토용이며 학생 게시판에 나타나지 않습니다."),
    field("유형", cat), field("내용", content), counter, btn);
  form.addEventListener("submit", busy(btn, async (e) => {
    e.preventDefault();
    try {
      const response = await fetch("/api/suggestions/anonymous", {
        method: "POST", credentials: "omit", referrerPolicy: "no-referrer",
        headers: { "Content-Type": "application/json", "X-Anonymous-Submit": "1" },
        body: JSON.stringify({ category: cat.value, content: content.value, is_public: visibility.value === "public" }),
      });
      const r = await response.json();
      if (!response.ok) throw new Error(r.message || "건의를 제출하지 못했습니다.");
      toast(r.message, "success");
      content.value = "";
      counter.textContent = "0 / 2000";
      visibility.value = "private";
    } catch (err) { errorToast(err); }
  }));
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "익명 건의함")), h("p", { class: "hint" }, "새 건의 접수 알림은 5~10분 뒤부터 교수자가 확인할 수 있으며, 앱 접속·기기 연결 상태에 따라 더 늦어질 수 있습니다. 알림에 작성자나 건의 내용은 포함하지 않지만, 알림 시점으로 제출 시간대를 추정할 수 있습니다."), form, h("a", { class: "btn", href: "/#/suggestions" }, "공개 건의 게시판 (로그인 필요)"));
}

const root = document.getElementById("view");
try {
  const response = await fetch("/api/auth/config", { credentials: "omit", cache: "no-store" });
  if (!response.ok) throw new Error("건의함을 열지 못했습니다. 다시 시도해 주세요.");
  if ((await response.json()).suggestions) await submitForm(root);
  else mount(root, h("p", {}, "현재 건의 접수가 중지되었습니다."));
} catch (error) {
  mount(root, h("p", { role: "alert" }, error.message));
}
