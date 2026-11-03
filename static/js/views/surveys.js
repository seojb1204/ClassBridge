// 설문 목록(교수자/학생), 응답 화면, 결과 화면
import { get, post } from "../api.js";
import { go } from "../router.js";
import { can } from "../state.js";
import { fmtDateTime } from "../time.js";
import { STATUS_LABEL, badge, empty, errorToast, h, mount, toast } from "../ui.js";
import { renderAnalysis } from "./analysis.js";
import { renderForm } from "./survey-form.js";

export async function renderList(root) {
  if (can("survey:manage")) return staffList(root);
  return studentList(root);
}

async function staffList(root) {
  const list = await get("/api/surveys");
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "설문"), h("a", { class: "btn primary", href: "#/surveys/edit/new" }, "+ 새 설문")),
    list.length ? h("div", { class: "cards" }, list.map((s) => h("div", { class: "card" },
      h("div", { class: "row" }, h("strong", {}, s.title), badge(STATUS_LABEL[s.status], s.status)),
      h("span", { class: "muted" }, `응답 ${s.response_count}건`, s.closes_at ? ` · 마감 ${fmtDateTime(s.closes_at)}` : ""),
      h("div", { class: "actions" },
        h("a", { class: "btn small", href: `#/surveys/edit/${s.id}` }, s.status === "draft" ? "편집" : "설정"),
        s.status !== "draft" ? h("a", { class: "btn small", href: `#/surveys/results/${s.id}` }, "결과") : null))))
      : empty("아직 설문이 없습니다."));
}

async function studentList(root) {
  const list = await get("/api/surveys/student/list");
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "설문")),
    list.length ? h("div", { class: "cards" }, list.map((s) => h("div", { class: "card" },
      h("div", { class: "row" }, h("strong", {}, s.title),
        s.participated ? badge("참여 완료", "completed") : s.is_open ? badge("응답 가능", "booked") : badge("마감", "cancelled")),
      s.closes_at ? h("span", { class: "muted" }, `마감 ${fmtDateTime(s.closes_at)}`) : null,
      s.is_open && !s.participated ? h("div", { class: "actions" },
        h("a", { class: "btn small primary", href: `#/surveys/take/${s.id}` }, "응답하기")) : null)))
      : empty("참여할 설문이 없습니다."));
}

export async function renderTake(root, { id }) {
  const s = await get(`/api/surveys/student/${id}`);
  if (s.participated) { mount(root, h("div", { class: "notice" }, "이미 참여한 설문입니다. 감사합니다.")); return; }
  if (!s.is_open) { mount(root, h("div", { class: "notice" }, "응답 기간이 아닙니다.")); return; }
  mount(root, renderForm(s, async (answers) => {
    try {
      const r = await post(`/api/surveys/${id}/responses`, { answers });
      toast(r.message, "success");
      mount(root, h("div", { class: "notice success" }, "응답이 익명으로 제출되었습니다. 감사합니다."),
        h("a", { class: "btn", href: "#/surveys" }, "설문 목록"));
    } catch (e) {
      errorToast(e);
      if (e.code === "already_participated") go("/surveys");
    }
  }));
}

export async function renderResults(root, { id }) {
  const r = await get(`/api/surveys/${id}/results`);
  const head = h("div", { class: "page-head" }, h("h1", {}, `결과: ${r.title}`),
    h("span", { class: "muted" }, `응답 ${r.response_count}건`));
  if (r.hidden) {
    mount(root, head, h("div", { class: "notice" },
      `응답이 ${r.min_results}건 이상 모이면 결과를 볼 수 있습니다. 소수 응답은 작성자가 드러날 수 있어 숨깁니다.`));
    return;
  }
  const analysisBox = h("div", {});
  mount(root, head,
    h("div", { class: "toolbar" },
      can("data:export") ? h("a", { class: "btn", href: `/api/surveys/${id}/export.xlsx` }, "엑셀 다운로드") : null,
      can("ai:analyze") ? h("button", { class: "btn", onclick: async () => {
        try { analysisBox.replaceChildren(renderAnalysis(await post("/api/analysis", { source: "survey", survey_id: +id }))); }
        catch (e) { errorToast(e); }
      } }, "자유응답 분석") : null),
    analysisBox,
    r.questions.map(questionResult));
}

function questionResult(q) {
  const total = Math.max(1, ...(q.counts || []).map((c) => c.count));
  return h("section", { class: "panel" }, h("h3", {}, q.title), h("p", { class: "muted" }, `응답 ${q.answered}건`,
    q.average != null ? ` · 평균 ${q.average}` : ""),
  q.counts ? h("div", { class: "bars" }, q.counts.map((c) => {
    const bar = h("span", { class: "bar-fill" });
    bar.style.width = `${(c.count / total) * 100}%`;
    return h("div", { class: "bar-row" }, h("span", { class: "bar-label" }, c.option), h("span", { class: "bar" }, bar),
      h("span", { class: "bar-n" }, String(c.count)));
  })) : h("ul", { class: "texts" }, (q.texts || []).map((t) => h("li", { class: "pre" }, t))));
}
