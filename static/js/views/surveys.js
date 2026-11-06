// 설문 목록(교수자/학생), 응답 화면, 결과 화면
import { get, post } from "../api.js";
import { go } from "../router.js";
import { can, feature } from "../state.js";
import { fmtDateTime } from "../time.js";
import { STATUS_LABEL, badge, empty, errorToast, h, mount, toast, confirmAction, promptText } from "../ui.js";
import { renderAnalysis } from "./analysis.js";
import { renderForm } from "./survey-form.js";
import { showSurveyQr } from "../components/survey-share.js";

export async function renderList(root) {
  if (can("survey:manage")) return staffList(root);
  return studentList(root);
}

let showTrash = false;
async function staffList(root) {
  const list = await get(`/api/surveys?trash=${showTrash}`);
  const manage = async (s, action) => {
    try {
      let body = {};
      if (action === "purge") {
        const word = await promptText("설문 영구 삭제", `‘${s.title}’의 문항, 답변 ${s.response_count}건, 참여 기록을 모두 삭제합니다. 복원할 수 없습니다. ‘영구 삭제’를 입력하세요.`);
        if (word !== "영구 삭제") return;
        body = { confirmation: word, response_count: s.response_count };
      } else if (!(await confirmAction(action === "trash" ? "설문 휴지통 이동" : "설문 복원",
        action === "trash" ? `‘${s.title}’과 답변 ${s.response_count}건을 휴지통으로 옮깁니다. 학생에게 숨겨지며 복원할 수 있습니다. 필요한 결과 파일은 먼저 내려받으세요.` : "이전 상태로 복원합니다. 종료된 설문은 다시 게시되지 않습니다.", "확인", action === "trash"))) return;
      await post(`/api/surveys/${s.id}/${action}`, body);
      await staffList(root);
    } catch (e) { errorToast(e); }
  };
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "설문"), h("a", { class: "btn primary", href: "#/surveys/edit/new" }, "+ 새 설문")),
    h("div", { class: "toolbar" },
      h("button", { class: showTrash ? "btn" : "btn primary", onclick: () => { showTrash = false; staffList(root); } }, "설문 목록"),
      h("button", { class: showTrash ? "btn primary" : "btn", onclick: () => { showTrash = true; staffList(root); } }, "휴지통")),
    list.length ? h("div", { class: "cards" }, list.map((s) => h("div", { class: "card" },
      h("div", { class: "row" }, h("strong", {}, s.title), badge(STATUS_LABEL[s.status], s.status)),
      h("span", { class: "muted" }, [s.course_name, s.semester].filter(Boolean).join(" · ")),
      h("span", { class: "muted" }, `응답 ${s.response_count}건`, s.closes_at ? ` · 마감 ${fmtDateTime(s.closes_at)}` : ""),
      h("div", { class: "actions" }, showTrash ? [
        h("button", { class: "btn", onclick: () => manage(s, "restore") }, "복원"),
        h("button", { class: "btn danger", onclick: () => manage(s, "purge") }, "영구 삭제"),
      ] : [
        h("a", { class: "btn small", href: `#/surveys/edit/${s.id}` }, s.status === "draft" ? "편집" : "설정"),
        s.status === "published" ? h("button", { class: "btn small", onclick: () => showSurveyQr(s) }, "QR 공유") : null,
        s.status !== "draft" ? h("a", { class: "btn small", href: `#/surveys/results/${s.id}` }, "결과") : null,
        s.status !== "published" ? h("button", { class: "btn small danger", onclick: () => manage(s, "trash") }, "휴지통으로")
          : h("span", { class: "hint" }, "삭제하려면 설정에서 먼저 설문을 종료하세요."),
      ])))) : empty(showTrash ? "휴지통이 비어 있습니다." : "아직 설문이 없습니다."));
}

async function studentList(root) {
  const list = await get("/api/surveys/student/list");
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "설문")),
    list.length ? h("div", { class: "cards" }, list.map((s) => h("div", { class: "card" },
      h("div", { class: "row" }, h("strong", {}, s.title),
        s.participated ? badge("참여 완료", "completed") : s.is_open ? badge(s.access_mode === "anonymous" ? "진행 중" : "응답 가능", "booked") : badge("마감", "cancelled")),
      h("span", { class: "muted" }, [s.course_name, s.semester].filter(Boolean).join(" · ")),
      s.access_mode === "anonymous" ? h("span", { class: "muted" }, "익명 설문 · 계정과 연결하지 않습니다. 참여 여부는 설문을 열면 확인됩니다.") : null,
      s.closes_at ? h("span", { class: "muted" }, `마감 ${fmtDateTime(s.closes_at)}`) : null,
      s.is_open && !s.participated ? h("div", { class: "actions" },
        h("a", { class: "btn small primary", href: s.access_mode === "anonymous" ? `#/surveys/public/${s.public_token}` : `#/surveys/take/${s.id}` },
          s.access_mode === "anonymous" ? "익명 설문 열기" : "응답하기")) : null)))
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
      can("ai:analyze") && ["demo", "external"].includes(feature("ai")) ? h("button", { class: "btn", onclick: async () => {
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

export async function renderPublic(root, token) {
  const endpoint = `/api/public-surveys/${token}`;
  try {
    const s = await get(endpoint);
    if (s.participated) { mount(root, h("p", { class: "notice" }, "이 브라우저에서는 이미 참여한 설문입니다. 감사합니다.")); return; }
    if (!s.is_open) { mount(root, h("p", { class: "notice" }, "응답 기간이 아니거나 종료된 설문입니다.")); return; }
    mount(root, renderForm(s, async (answers) => {
      try {
        const response = await fetch(`${endpoint}/responses`, { method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-Survey-CSRF": s.csrf_token }, body: JSON.stringify({ answers }) });
        const result = await response.json();
        if (!response.ok) { toast(result.message || "제출하지 못했습니다. 다시 시도해 주세요.", "error"); return; }
        mount(root, h("div", { class: "notice success" }, "응답이 제출되었습니다. 감사합니다. 창을 닫으셔도 됩니다."));
      } catch { toast("인터넷 연결을 확인해 주세요. 제출 결과는 설문을 다시 열어 확인할 수 있습니다.", "error"); }
    }));
  } catch (error) { mount(root, h("p", { class: "notice" }, error.message || "설문을 열 수 없습니다.")); }
}
