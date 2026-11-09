// 익명 건의함: 학생 제출 / 교수자·관리자 열람
import { get, post, put } from "../api.js";
import { can, feature } from "../state.js";
import { fmtDate } from "../time.js";
import { STATUS_LABEL, badge, busy, empty, errorToast, h, mount, select, confirmAction, promptText } from "../ui.js";
import { renderAnalysis } from "./analysis.js";

import { CATS } from "../suggestion-categories.js";
const CAT_LABEL = Object.fromEntries(CATS);
let filter = { status: "", category: "" };
let trash = false;
let pageOffset = 0;
const PAGE_SIZE = 50;

export async function render(root) {
  if (can("suggestion:read")) return inbox(root);
  mount(root, h("a", { class: "btn primary", href: "/static/suggest.html" }, "익명 건의하기"));
  const board = h("section", { class: "public-board" });
  root.append(board);
  await loadPublic(board);
}

async function inbox(root) {
  const q = new URLSearchParams({ trash, limit: PAGE_SIZE, offset: pageOffset });
  if (filter.status) q.set("status", filter.status);
  if (filter.category) q.set("category", filter.category);
  const [list, stats] = await Promise.all([get(`/api/suggestions?${q}`), get("/api/suggestions/stats")]);
  const st = select([["", "전체 상태"], ["new", "새 건의"], ["reviewed", "확인함"], ["archived", "보관"]], filter.status);
  const ct = select([["", "전체 유형"], ...CATS], filter.category);
  const apply = () => { pageOffset = 0; filter = { status: st.value, category: ct.value }; inbox(root); };
  st.addEventListener("change", apply);
  ct.addEventListener("change", apply);
  const analysisBox = h("div", {});
  const aBtn = h("button", { class: "btn" }, "반복 의견 분석");
  aBtn.addEventListener("click", busy(aBtn, async () => {
    try { analysisBox.replaceChildren(renderAnalysis(await post("/api/analysis", { source: "suggestions" }))); }
    catch (e) { errorToast(e); }
  }));
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "건의함"), h("span", { class: "muted" }, `전체 ${stats.total}건`)),
    h("div", { class: "toolbar" },
      h("button", { class: trash ? "btn" : "btn primary", onclick: () => { trash = false; pageOffset = 0; inbox(root); } }, "건의 목록"),
      h("button", { class: trash ? "btn primary" : "btn", onclick: () => { trash = true; pageOffset = 0; inbox(root); } }, "휴지통")),
    h("div", { class: "stats" }, CATS.map(([k, label]) => h("span", { class: "stat" }, label, h("strong", {}, String(stats.by_category[k] || 0))))),
    h("div", { class: "filters" }, st, ct, can("ai:analyze") && ["demo", "external"].includes(feature("ai")) ? aBtn : null),
    analysisBox,
    list.length ? h("div", { class: "cards" }, list.map((s) => card(root, s))) : empty(trash ? "휴지통이 비어 있습니다." : "건의가 없습니다."), pager(() => inbox(root), list.length));
}

function card(root, s) {
  const setStatus = async (status) => {
    try { await put(`/api/suggestions/${s.id}/status`, { status }); await inbox(root); } catch (e) { errorToast(e); }
  };
  return h("div", { class: "card" },
    h("div", { class: "row" }, h("span", {}, badge(CAT_LABEL[s.category]), " ", h("span", { class: "muted" }, fmtDate(s.submitted_on))),
      badge(s.replies.length ? "답변 완료" : s.status === "reviewed" ? "검토 중" : STATUS_LABEL[s.status], s.status)),
    h("span", { class: "badge" }, s.is_public ? "로그인 이용자 공개" : "비공개"),
    h("p", { class: "pre" }, s.content), replyList(s),
    managementButtons(root, s),
    trash ? null : h("div", { class: "actions" },
      s.status !== "reviewed" ? h("button", { class: "btn small", onclick: () => setStatus("reviewed") }, "확인함") : null,
      s.status !== "archived" ? h("button", { class: "btn small", onclick: () => setStatus("archived") }, "보관") : null,
      s.status !== "new" ? h("button", { class: "btn small", onclick: () => setStatus("new") }, "새 건의로") : null));
}


function pager(refresh, count) {
  return h("div", { class: "toolbar" },
    h("button", { class: "btn", disabled: pageOffset === 0, onclick: () => { pageOffset -= PAGE_SIZE; refresh(); } }, "이전 건의"),
    h("span", {}, `${Math.floor(pageOffset / PAGE_SIZE) + 1} 페이지`),
    h("button", { class: "btn", disabled: count < PAGE_SIZE, onclick: () => { pageOffset += PAGE_SIZE; refresh(); } }, "다음 건의"));
}

function replyList(s) {
  return h("div", { class: "suggestion-replies" }, s.replies.map((r) => h("section", { class: "notice" },
    h("strong", {}, "교수자 답변"), h("small", { class: "muted" }, ` · ${fmtDate(r.created_on)}`),
    h("p", { class: "pre" }, r.content))));
}

function managementButtons(root, s) {
  const action = async (name) => {
    try {
      let body = {};
      if (name === "purge") {
        const word = await promptText("건의 영구 삭제", "내용과 모든 답변을 영구 삭제합니다. 복원할 수 없습니다. ‘영구 삭제’를 입력하세요.");
        if (word !== "영구 삭제") return;
        body = { confirmation: word };
      } else if (!(await confirmAction(name === "trash" ? "휴지통 이동" : "건의 복원",
        name === "trash" ? "게시판에서 숨깁니다. 휴지통에서 복원할 수 있습니다." : "기존 공개 범위로 복원합니다.", "확인", name === "trash"))) return;
      await post(`/api/suggestions/${s.id}/${name}`, body);
      await inbox(root);
    } catch (e) { errorToast(e); }
  };
  return h("div", { class: "actions" }, trash ? [
    h("button", { class: "btn", onclick: () => action("restore") }, "복원"),
    h("button", { class: "btn danger", onclick: () => action("purge") }, "영구 삭제"),
  ] : [
    h("button", { class: "btn", onclick: async () => {
      const content = await promptText("교수자 답변", s.is_public ? "모든 로그인 이용자에게 공개됩니다. 개인 상담 정보는 적지 마세요." : "비공개 건의의 내부 답변입니다. 교수자·관리자만 볼 수 있습니다.", { multiline: true });
      if (!content?.trim()) return;
      try { await post(`/api/suggestions/${s.id}/replies`, { content }); await inbox(root); } catch (e) { errorToast(e); }
    } }, "답변 달기"),
    h("button", { class: "btn danger", onclick: () => action("trash") }, "휴지통으로"),
  ]);
}

async function loadPublic(root) {
  try {
    const list = await get(`/api/suggestions/public?limit=${PAGE_SIZE}&offset=${pageOffset}`);
    mount(root, h("h2", {}, "공개 건의 게시판"), h("p", { class: "muted" }, "작성자가 공개를 선택한 건의입니다. 모든 로그인 이용자가 볼 수 있으며 교수자·관리자만 답변합니다."),
      list.length ? h("div", { class: "cards" }, list.map((s) => h("article", { class: "card" },
        h("div", { class: "row" }, badge(CAT_LABEL[s.category]), badge(s.replies.length ? "답변 완료" : "접수")),
        h("p", { class: "pre" }, s.content), replyList(s)))) : empty("공개된 건의가 없습니다."),
      pager(() => loadPublic(root), list.length));
  } catch (e) { mount(root, h("p", { class: "error-box" }, e.message)); }
}
