// 익명 건의함: 학생 제출 / 교수자·관리자 열람
import { get, post, put } from "../api.js";
import { can } from "../state.js";
import { fmtDate } from "../time.js";
import { STATUS_LABEL, badge, busy, empty, errorToast, field, h, mount, select, toast } from "../ui.js";
import { renderAnalysis } from "./analysis.js";

const CATS = [["lecture", "강의"], ["assignment", "과제"], ["exam", "시험"], ["facility", "시설·환경"], ["other", "기타"]];
const CAT_LABEL = Object.fromEntries(CATS);
let filter = { status: "", category: "" };

export async function render(root) {
  if (can("suggestion:read")) return inbox(root);
  return submitForm(root);
}

function submitForm(root) {
  const cat = select(CATS, "lecture");
  const content = h("textarea", { rows: 6, maxlength: 2000, required: true, placeholder: "자유롭게 의견을 남겨 주세요." });
  const counter = h("small", { class: "hint" }, "0 / 2000");
  content.addEventListener("input", () => { counter.textContent = `${content.value.length} / 2000`; });
  const btn = h("button", { class: "btn primary", type: "submit" }, "익명으로 제출");
  const form = h("form", { class: "panel" },
    h("p", { class: "muted" }, "작성자 정보와 제출 시각은 저장되지 않습니다(날짜만 저장). 교수자·관리자만 내용을 볼 수 있습니다."),
    field("유형", cat), field("내용", content), counter, btn);
  form.addEventListener("submit", busy(btn, async (e) => {
    e.preventDefault();
    try {
      const r = await post("/api/suggestions", { category: cat.value, content: content.value });
      toast(r.message, "success");
      content.value = "";
      counter.textContent = "0 / 2000";
    } catch (err) { errorToast(err); }
  }));
  mount(root, h("div", { class: "page-head" }, h("h1", {}, "익명 건의함")), form);
}

async function inbox(root) {
  const q = new URLSearchParams();
  if (filter.status) q.set("status", filter.status);
  if (filter.category) q.set("category", filter.category);
  const [list, stats] = await Promise.all([get(`/api/suggestions?${q}`), get("/api/suggestions/stats")]);
  const st = select([["", "전체 상태"], ["new", "새 건의"], ["reviewed", "확인함"], ["archived", "보관"]], filter.status);
  const ct = select([["", "전체 유형"], ...CATS], filter.category);
  const apply = () => { filter = { status: st.value, category: ct.value }; inbox(root); };
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
    h("div", { class: "stats" }, CATS.map(([k, label]) => h("span", { class: "stat" }, label, h("strong", {}, String(stats.by_category[k] || 0))))),
    h("div", { class: "filters" }, st, ct, can("ai:analyze") ? aBtn : null),
    analysisBox,
    list.length ? h("div", { class: "cards" }, list.map((s) => card(root, s))) : empty("건의가 없습니다."));
}

function card(root, s) {
  const setStatus = async (status) => {
    try { await put(`/api/suggestions/${s.id}/status`, { status }); await inbox(root); } catch (e) { errorToast(e); }
  };
  return h("div", { class: "card" },
    h("div", { class: "row" }, h("span", {}, badge(CAT_LABEL[s.category]), " ", h("span", { class: "muted" }, fmtDate(s.submitted_on))),
      badge(STATUS_LABEL[s.status], s.status)),
    h("p", { class: "pre" }, s.content),
    h("div", { class: "actions" },
      s.status !== "reviewed" ? h("button", { class: "btn small", onclick: () => setStatus("reviewed") }, "확인함") : null,
      s.status !== "archived" ? h("button", { class: "btn small", onclick: () => setStatus("archived") }, "보관") : null,
      s.status !== "new" ? h("button", { class: "btn small", onclick: () => setStatus("new") }, "새 건의로") : null));
}
