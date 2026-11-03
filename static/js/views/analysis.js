// 의견 분석 결과 표시 (로컬 키워드 분석 / 외부 AI)
import { h } from "../ui.js";

const KIND = { positive: "긍정", improvement: "개선", other: "기타", keyword: "키워드" };

export function renderAnalysis(r) {
  return h("section", { class: "panel analysis" },
    h("h3", {}, "의견 분석"),
    r.notice ? h("p", { class: "muted" }, r.notice) : null,
    h("p", {}, r.summary),
    r.classification ? h("p", { class: "muted" },
      `긍정 ${r.classification.positive} · 개선 ${r.classification.improvement} · 기타 ${r.classification.other}`) : null,
    r.themes?.length ? h("ul", { class: "themes" }, r.themes.map((t) => h("li", {},
      h("strong", {}, t.title), ` (${KIND[t.kind] || t.kind}, ${t.count}건)`,
      h("ul", {}, t.examples.map((e) => h("li", { class: "quote" }, `“${e}”`)))))) : h("p", { class: "muted" }, "반복되는 주제가 없습니다."),
    r.actions?.length ? h("div", {}, h("h4", {}, "제안 (AI 생성, 확인 필요)"), h("ul", {}, r.actions.map((a) => h("li", {}, a)))) : null);
}
