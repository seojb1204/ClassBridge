// 설문 응답 폼 렌더러 (학생 응답 화면과 편집기 미리보기에서 공용)
import { h } from "../ui.js";
import { scaleLabels } from "../survey-scale.js";

export function renderForm(survey, onSubmit, { disabled = false } = {}) {
  const getters = [];
  const summary = h("div", { class: "error-box", role: "alert", tabindex: -1, hidden: true });
  const form = h("form", { class: "survey-form" }, summary,
    h("div", { class: "panel" }, h("h2", {}, survey.title || "(제목 없음)"),
      survey.description ? h("p", { class: "pre" }, survey.description) : null,
      h("p", { class: "muted" }, survey.access_mode === "anonymous"
        ? "로그인 없이 참여하는 설문입니다. 이름·계정은 수집하지 않습니다. 같은 브라우저의 중복 제출 확인용 쿠키와 참여 기록은 답변과 별도로 저장합니다. 쿠키 삭제·다른 기기의 반복 참여까지 막지는 못합니다. * 표시는 필수 문항입니다."
        : "참여는 선택입니다. 중복 제출 방지를 위한 참여 여부는 답변과 별도로 저장하며, 교수자·관리자 화면에는 답변 작성자 정보가 표시되지 않습니다. * 표시는 문항의 필수 입력 표시입니다."),
      h("p", { class: "hint" }, "이름·학번·연락처나 건강·심리 상태 등 민감정보를 적지 마세요. 내용이나 DB·서버 기록으로 작성자를 추정할 가능성까지 없애지는 못합니다."),
      h("a", { href: "/privacy", target: "_blank", rel: "noopener" }, "개인정보처리방침")),
    survey.questions.map((q) => {
      const { node, value } = input(q, disabled);
      const legendId = `question-${q.id}-label`, errorId = `question-${q.id}-error`;
      const controls = node.matches("input, textarea, select") ? [node] : [...node.querySelectorAll("input")];
      if (node.matches("input, textarea, select")) node.setAttribute("aria-labelledby", legendId);
      const error = h("p", { id: errorId, class: "error-box", hidden: true }, "이 필수 문항에 답해 주세요.");
      controls.forEach(control => control.setAttribute("aria-describedby", errorId));
      getters.push([q, value, controls, error]);
      const clear = !q.required && ["single", "scale5"].includes(q.qtype)
        ? h("button", { class: "btn small", type: "button", disabled, onclick: () => {
          controls.forEach(control => { control.checked = false; });
        } }, "선택 해제") : null;
      return h("fieldset", { class: "q-card" }, h("legend", { id: legendId }, q.title,
        q.required ? h("span", { class: "req" }, " *") : null), node, error, clear);
    }));
  const btn = h("button", { class: "btn primary", type: "submit", disabled }, "제출");
  form.append(btn);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (btn.disabled) return;
    const answers = {};
    const missing = [];
    for (const [q, value, controls, error] of getters) {
      const answer = value();
      answers[String(q.id)] = answer;
      const invalid = q.required && (answer == null || (typeof answer === "string" && !answer.trim())
        || (Array.isArray(answer) && !answer.length));
      error.hidden = !invalid;
      controls.forEach(control => control.setAttribute("aria-invalid", String(Boolean(invalid))));
      if (invalid) missing.push([q, controls[0]]);
    }
    summary.hidden = !missing.length;
    if (missing.length) {
      summary.replaceChildren(h("strong", {}, `필수 문항 ${missing.length}개를 확인해 주세요.`),
        h("ul", {}, missing.map(([q, control]) => h("li", {}, h("button", {
          class: "btn small", type: "button", onclick: () => control?.focus(),
        }, q.title)))));
      summary.focus();
      return;
    }
    btn.disabled = true;
    try { await onSubmit(answers); } finally { btn.disabled = disabled; }
  });
  return form;
}

function input(q, disabled) {
  const name = `q-${q.id}`;
  switch (q.qtype) {
    case "short": {
      const el = h("input", { type: "text", maxlength: 500, disabled, name });
      return { node: el, value: () => el.value };
    }
    case "long": {
      const el = h("textarea", { rows: 4, maxlength: 5000, disabled, name });
      return { node: el, value: () => el.value };
    }
    case "dropdown": {
      const el = h("select", { disabled, name }, h("option", { value: "" }, "선택"), q.options.map((o) => h("option", { value: o }, o)));
      return { node: el, value: () => el.value || null };
    }
    case "single":
    case "multi": {
      const type = q.qtype === "single" ? "radio" : "checkbox";
      const items = q.options.map((o) => h("label", { class: "check" }, h("input", { type, name, value: o, disabled }), o));
      return { node: h("div", { class: "choices" }, items), value: () => {
        const sel = items.map((l) => l.firstChild).filter((x) => x.checked).map((x) => x.value);
        return q.qtype === "single" ? (sel[0] ?? null) : sel;
      } };
    }
    case "scale5": {
      const items = scaleLabels(q).map((label, i) => h("label", { class: "check" },
        h("input", { type: "radio", name, value: i + 1, disabled }), `${i + 1} · ${label}`));
      return { node: h("div", { class: "choices scale-choices" }, items),
        value: () => { const x = items.map((l) => l.firstChild).find((i) => i.checked); return x ? +x.value : null; } };
    }
    default:
      return { node: h("p", {}, "지원하지 않는 문항"), value: () => null };
  }
}
