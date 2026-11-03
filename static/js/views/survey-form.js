// 설문 응답 폼 렌더러 (학생 응답 화면과 편집기 미리보기에서 공용)
import { h } from "../ui.js";

export function renderForm(survey, onSubmit, { disabled = false } = {}) {
  const getters = [];
  const form = h("form", { class: "survey-form" },
    h("div", { class: "panel" }, h("h2", {}, survey.title || "(제목 없음)"),
      survey.description ? h("p", { class: "pre" }, survey.description) : null,
      h("p", { class: "muted" }, "응답은 익명으로 저장되며 작성자와 연결되지 않습니다. * 표시는 필수입니다.")),
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
      const items = [1, 2, 3, 4, 5].map((n) => h("label", { class: "scale-item" }, h("input", { type: "radio", name, value: n, disabled }), String(n)));
      return { node: h("div", { class: "scale" }, h("span", { class: "muted" }, "매우 불만"), items, h("span", { class: "muted" }, "매우 만족")),
        value: () => { const x = items.map((l) => l.firstChild).find((i) => i.checked); return x ? +x.value : null; } };
    }
    default:
      return { node: h("p", {}, "지원하지 않는 문항"), value: () => null };
  }
}
