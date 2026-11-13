// 익명 건의함: 학생 제출 / 교수자·관리자 열람
import { get, post, put } from "../api.js";
import { can, feature } from "../state.js";
import { fmtDate } from "../time.js";
import { STATUS_LABEL, badge, busy, empty, errorToast, h, mount, select, confirmAction, promptText, modal } from "../ui.js";
import { renderAnalysis } from "./analysis.js";

import { CATS } from "../suggestion-categories.js";
const CAT_LABEL = Object.fromEntries(CATS);
let filter = { status: "", category: "", query: "", order: "newest" };
let trash = false;
let pageOffset = 0;
const PAGE_SIZE = 50;
let inboxVersion = 0;

async function confirmPermanent(title, message) {
  return (await modal(title, h("p", {}, message), [
    { label: "아니요", value: false }, { label: "예, 영구 삭제", value: true, danger: true },
  ])) === true;
}

export async function render(root) {
  if (can("suggestion:read")) return inbox(root);
  mount(root, h("a", { class: "btn primary", href: "/static/suggest.html" }, "익명 건의하기"));
  const board = h("section", { class: "public-board" });
  root.append(board);
  await loadPublic(board);
}

async function inbox(root) {
  const version = ++inboxVersion;
  const path = location.hash;
  const isCurrent = () => version === inboxVersion && location.hash === path && root.isConnected;
  const q = new URLSearchParams({ trash, limit: PAGE_SIZE, offset: pageOffset, order: filter.order });
  if (filter.status) q.set("status", filter.status);
  if (filter.category) q.set("category", filter.category);
  const listRequest = filter.query ? post("/api/suggestions/search", {
    query: filter.query, status: filter.status || null, category: filter.category || null,
    order: filter.order, trash, limit: PAGE_SIZE, offset: pageOffset,
  }) : get(`/api/suggestions?${q}`);
  let list, stats;
  try { [list, stats] = await Promise.all([listRequest, get("/api/suggestions/stats")]); }
  catch (e) { if (isCurrent()) throw e; else return; }
  if (!isCurrent()) return;
  const st = select([["", "전체 상태"], ["new", "새 건의"], ["reviewed", "검토 중"], ["archived", "보관"]], filter.status);
  const ct = select([["", "전체 유형"], ...CATS], filter.category);
  st.setAttribute("aria-label", "건의 상태");
  ct.setAttribute("aria-label", "건의 유형");
  const order = select([["newest", "최근 접수일 먼저"], ["oldest", "오래된 접수일 먼저"]], filter.order);
  order.setAttribute("aria-label", "건의 정렬");
  const search = h("input", { type: "search", value: filter.query, maxlength: 200,
    placeholder: "건의 내용 검색", "aria-label": "건의 내용 검색" });
  const reload = async () => { if (location.hash !== path || !root.isConnected) return; try { await inbox(root); } catch (e) { errorToast(e); } };
  const apply = () => { pageOffset = 0; filter = { ...filter, status: st.value, category: ct.value, order: order.value }; reload(); };
  order.addEventListener("change", apply);
  const searchForm = h("form", { class: "toolbar suggestion-search", role: "search" }, search,
    h("button", { type: "submit", class: "btn" }, "검색"),
    h("button", { type: "button", class: "btn", onclick: () => { filter.query = ""; pageOffset = 0; reload(); } }, "검색 지우기"));
  searchForm.addEventListener("submit", e => { e.preventDefault(); filter.query = search.value.trim(); pageOffset = 0; reload(); });
  const statusTabs = h("div", { class: "toolbar", "aria-label": "건의 상태 빠른 필터" },
    ...[["", "전체"], ["new", "새 건의"], ["reviewed", "검토 중"], ["archived", "보관"]].map(([value, label]) =>
      h("button", { type: "button", class: filter.status === value ? "btn primary" : "btn",
        "aria-pressed": String(filter.status === value), onclick: () => { filter.status = value; pageOffset = 0; reload(); } },
      `${label} ${value ? stats.by_status[value] || 0 : stats.total}`)));
  st.addEventListener("change", apply);
  ct.addEventListener("change", apply);
  const analysisBox = h("div", {});
  const aBtn = h("button", { class: "btn" }, "반복 의견 분석");
  aBtn.addEventListener("click", busy(aBtn, async () => {
    try { analysisBox.replaceChildren(renderAnalysis(await post("/api/analysis", { source: "suggestions" }))); }
    catch (e) { errorToast(e); }
  }));
  const emptyTrash = h("button", { class: "btn danger", type: "button" }, "휴지통 비우기");
  emptyTrash.onclick = busy(emptyTrash, async () => {
    try {
      const snapshot = await get("/api/suggestions/trash/preview");
      if (!isCurrent()) return;
      if (!snapshot.count) { await reload(); return; }
      const confirmed = await confirmPermanent("휴지통 비우기",
        `현재 휴지통 전체 ${snapshot.count}건과 모든 답변·내부 메모를 영구 삭제할까요? 검색 조건이나 현재 페이지와 관계없이 포함하며 복원할 수 없습니다. 확인 목록에 없는 다른 건의는 삭제하지 않습니다.`);
      if (!confirmed || !isCurrent()) return;
      await post("/api/suggestions/trash/empty", { confirmation: "영구 삭제", ids: snapshot.ids });
      if (isCurrent()) { pageOffset = 0; await reload(); }
    } catch (e) { errorToast(e); }
  });
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "건의함"), h("span", { class: "muted" }, `전체 ${stats.total}건`)),
    h("div", { class: "toolbar" },
      h("button", { class: trash ? "btn" : "btn primary", onclick: () => { trash = false; pageOffset = 0; reload(); } }, "건의 목록"),
      h("button", { class: trash ? "btn primary" : "btn", onclick: () => { trash = true; pageOffset = 0; reload(); } }, "휴지통"), trash ? emptyTrash : null),
    h("div", { class: "stats" }, CATS.map(([k, label]) => h("span", { class: "stat" }, label, h("strong", {}, String(stats.by_category[k] || 0))))),
    trash ? null : statusTabs,
    searchForm,
    h("p", { class: "hint" }, "접수일 기준으로 정렬합니다. 익명성 보호를 위해 같은 날의 접수 순서는 표시하지 않습니다."),
    h("div", { class: "filters" }, st, ct, order, can("ai:analyze") && ["demo", "external"].includes(feature("ai")) ? aBtn : null),
    analysisBox,
    list.length ? h("div", { class: "cards" }, list.map((s) => card(root, s))) : empty(trash ? "휴지통이 비어 있습니다." : "건의가 없습니다."), pager(reload, list.length));
}

function card(root, s) {
  const path = location.hash;
  const setStatus = async (status) => {
    try { await put(`/api/suggestions/${s.id}/status`, { status }); if (location.hash === path) await inbox(root); } catch (e) { errorToast(e); }
  };
  return h("div", { class: "card" },
    h("div", { class: "row" }, h("span", {}, badge(CAT_LABEL[s.category]), " ", h("span", { class: "muted" }, fmtDate(s.submitted_on))),
      badge(s.status === "reviewed" ? "검토 중" : STATUS_LABEL[s.status], s.status)),
    badge(s.replies.length ? `${s.is_public ? "답변" : "내부 메모"} ${s.replies.length}개` : s.is_public ? "미답변" : "내부 메모 없음"),
    h("span", { class: "badge" }, s.is_public ? "로그인 이용자 공개" : "비공개"),
    s.content.length > 160 ? h("div", {}, h("p", { class: "pre" }, s.content.slice(0, 160) + "…"),
      h("details", {}, h("summary", {}, "건의 내용 전체 보기"), h("p", { class: "pre" }, s.content)))
      : h("p", { class: "pre" }, s.content), replyList(s),
    managementButtons(root, s),
    trash ? null : h("div", { class: "actions" },
      s.status !== "reviewed" ? h("button", { class: "btn small", onclick: () => setStatus("reviewed") }, "검토 중으로") : null,
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
    h("strong", {}, s.is_public ? "교수자 답변" : "내부 메모 · 학생에게 전달되지 않음"), h("small", { class: "muted" }, ` · ${fmtDate(r.created_on)}`),
    h("p", { class: "pre" }, r.content))));
}

function managementButtons(root, s) {
  const path = location.hash, version = inboxVersion;
  let pending = false;
  const action = async (name) => {
    if (pending) return;
    pending = true;
    try {
      let body = {};
      if (name === "purge") {
        if (!(await confirmPermanent("건의 영구 삭제", "이 건의 1건과 모든 답변·내부 메모를 영구 삭제할까요? 복원할 수 없습니다."))) return;
        body = { confirmation: "영구 삭제" };
      } else if (!(await confirmAction(name === "trash" ? "휴지통 이동" : "건의 복원",
        name === "trash" ? "게시판에서 숨깁니다. 휴지통에서 복원할 수 있습니다." : "기존 공개 범위로 복원합니다.", "확인", name === "trash"))) return;
      if (location.hash !== path || !root.isConnected || inboxVersion !== version) return;
      await post(`/api/suggestions/${s.id}/${name}`, body);
      if (location.hash === path) await inbox(root);
    } catch (e) { errorToast(e); }
    finally { pending = false; }
  };
  return h("div", { class: "actions" }, trash ? [
    h("button", { class: "btn", onclick: () => action("restore") }, "복원"),
    h("button", { class: "btn danger", onclick: () => action("purge") }, "영구 삭제"),
  ] : [
    h("button", { class: "btn", onclick: async () => {
      const content = await promptText(s.is_public ? "교수자 답변" : "내부 메모", s.is_public ? "모든 로그인 이용자에게 공개됩니다. 개인 상담 정보는 적지 마세요." : "학생에게 전달되지 않는 내부 메모입니다. 교수자·관리자만 볼 수 있습니다.", { multiline: true });
      if (!content?.trim()) return;
      try { await post(`/api/suggestions/${s.id}/replies`, { content }); if (location.hash === path) await inbox(root); } catch (e) { errorToast(e); }
    } }, s.is_public ? "답변 달기" : "내부 메모"),
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
