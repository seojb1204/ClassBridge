// 설문 응답 폼 렌더러 (학생 응답 화면과 편집기 미리보기에서 공용)
import { h } from "../ui.js";
import { scaleLabels } from "../survey-scale.js";

export function renderForm(survey, onSubmit, { disabled = false } = {}) {
  const getters = [];
  const form = h("form", { class: "survey-form" },
    h("div", { class: "panel" }, h("h2", {}, survey.title || "(제목 없음)"),
      survey.description ? h("p", { class: "pre" }, survey.description) : null,
      h("p", { class: "muted" }, survey.access_mode === "anonymous"
        ? "로그인 없이 참여하는 설문입니다. 이름·계정은 수집하지 않습니다. 같은 브라우저의 중복 제출 확인용 쿠키와 참여 기록은 답변과 별도로 저장합니다. 쿠키 삭제·다른 기기의 반복 참여까지 막지는 못합니다. * 표시는 필수 문항입니다."
        : "참여는 선택입니다. 중복 제출 방지를 위한 참여 여부는 답변과 별도로 저장하며, 교수자·관리자 화면에는 답변 작성자 정보가 표시되지 않습니다. * 표시는 문항의 필수 입력 표시입니다."),
      h("p", { class: "hint" }, "이름·학번·연락처나 건강·심리 상태 등 민감정보를 적지 마세요. 내용이나 DB·서버 기록으로 작성자를 추정할 가능성까지 없애지는 못합니다."),
      h("a", { href: "/privacy", target: "_blank", rel: "noopener" }, "개인정보처리방침")),
    survey.questions.map((q) => {
      const { node, value } = input(q, disabled);
      getters.push([q, value]);
      return h("fieldset", { class: "q-card" }, h("legend", {}, q.title, q.required ? h("span", { class: "req" }, " *") : null), node);
    }));
  const btn = h("button", { class: "btn primary", type: "submit", disabled }, "제출");
  form.append(btn);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (btn.disabled) return;
    const answers = {};
    for (const [q, value] of getters) answers[String(q.id)] = value();
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
