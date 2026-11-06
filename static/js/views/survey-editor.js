// 교수자·관리자: 구글폼형 설문 편집기 (초안에서만 문항 편집, 게시 후 잠금)
import { get, patch, post } from "../api.js";
import { go } from "../router.js";
import { isoToKstInput, kstInputToIso } from "../time.js";
import { STATUS_LABEL, badge, busy, confirmAction, errorToast, field, h, mount, select, toast } from "../ui.js";
import { renderForm } from "./survey-form.js";
import { AGREEMENT_SCALE, scaleLabels } from "../survey-scale.js";
import { showSurveyQr, surveyUrl } from "../components/survey-share.js";

const TYPES = [["long", "직접 입력 (소감형)"], ["scale5", "5점 척도"], ["single", "선택지 고르기 (1개)"]];
const LEGACY_TYPES = {short: "기존 단답형", multi: "기존 복수 선택", dropdown: "기존 드롭다운"};
const CHOICE = new Set(["single", "multi", "dropdown"]);

export async function render(root, { id }) {
  const s = id === "new" ? { id: null, title: "", description: "", course_name: "", semester: "",
    status: "draft", questions: [], min_results: 5, access_mode: "login",
    opens_at: null, closes_at: null } : await get(`/api/surveys/${id}`);
  const model = structuredClone(s);
  const locked = s.status !== "draft";
  const access = select([["login", "로그인 필요 (Google 계정당 1회)"], ["anonymous", "익명 참여 (로그인 없음)"]], model.access_mode);
  access.disabled = locked;
  let preview = false;

  const title = h("input", { type: "text", class: "title-input", maxlength: 200, placeholder: "설문 제목", value: model.title });
  const desc = h("textarea", { rows: 2, maxlength: 5000, placeholder: "설명 (선택)" });
  desc.value = model.description;
  const course = h("input", { type: "text", maxlength: 120, value: model.course_name || "", disabled: locked,
    placeholder: "교과목 (예: 항공서비스 실무)" });
  const semester = h("input", { type: "text", maxlength: 40, value: model.semester || "", disabled: locked,
    placeholder: "학기 (예: 2026-2)" });
  const opens = h("input", { type: "datetime-local", value: isoToKstInput(model.opens_at), disabled: locked });
  const closes = h("input", { type: "datetime-local", value: isoToKstInput(model.closes_at), disabled: s.status === "closed" });
  const minRes = h("input", { type: "number", min: 1, max: 50, value: model.min_results, disabled: locked });
  const qBox = h("div", { class: "questions" });
  const body = h("div", {});

  function drawQuestions() {
    qBox.replaceChildren(...model.questions.map((q, i) => questionCard(q, i)));
    if (!locked) qBox.append(h("button", { class: "btn add-q", onclick: () => {
      model.questions.push({ qtype: "long", title: "", required: false, options: [] });
      drawQuestions();
      qBox.querySelectorAll(".q-title")[model.questions.length - 1]?.focus();
    } }, "+ 문항 추가"));
  }

  function questionCard(q, i) {
    const t = h("input", { type: "text", class: "q-title", maxlength: 500, placeholder: `${i + 1}번 문항`, value: q.title, disabled: locked });
    t.addEventListener("input", () => { q.title = t.value; });
    const type = select(LEGACY_TYPES[q.qtype] ? [...TYPES, [q.qtype, LEGACY_TYPES[q.qtype]]] : TYPES, q.qtype);
    type.setAttribute("aria-label", `${i + 1}번 문항 유형`);
    type.disabled = locked;
    type.addEventListener("change", () => {
      q.qtype = type.value;
      q.options = q.qtype === "scale5" ? [...AGREEMENT_SCALE] : CHOICE.has(q.qtype) ? ["선택지 1", "선택지 2"] : [];
      drawQuestions();
    });
    const req = h("input", { type: "checkbox", checked: q.required, disabled: locked });
    req.addEventListener("change", () => { q.required = req.checked; });
    const move = (d) => {
      const j = i + d;
      if (j < 0 || j >= model.questions.length) return;
      [model.questions[i], model.questions[j]] = [model.questions[j], model.questions[i]];
      drawQuestions();
    };
    return h("div", { class: "q-card" },
      h("div", { class: "q-row" }, t, type),
      CHOICE.has(q.qtype) ? optionsEditor(q) : h("p", { class: "muted" },
        q.qtype === "scale5" ? scaleLabels(q).map((label, index) => `${index + 1} ${label}`).join(" / ") +
          " · 예: 강의 설명이 이해하기 쉬웠다. 한 문항에는 한 가지 내용만 질문하세요."
          : q.qtype === "long" ? "학생이 직접 소감을 입력합니다. 예: 이번 강의에서 개선할 점을 적어 주세요." : "기존 단답 응답"),
      h("div", { class: "q-foot" },
        h("label", { class: "check" }, req, "필수"),
        locked ? null : h("span", { class: "q-tools" },
          h("button", { class: "link", onclick: () => move(-1), "aria-label": "위로" }, "▲"),
          h("button", { class: "link", onclick: () => move(1), "aria-label": "아래로" }, "▼"),
          h("button", { class: "link danger", onclick: () => { model.questions.splice(i, 1); drawQuestions(); } }, "삭제"))));
  }

  function optionsEditor(q) {
    const box = h("div", { class: "options" });
    q.options.forEach((o, k) => {
      const inp = h("input", { type: "text", value: o, maxlength: 200, disabled: locked });
      inp.addEventListener("input", () => { q.options[k] = inp.value; });
      box.append(h("div", { class: "opt" }, h("span", { class: "dot" }, q.qtype === "multi" ? "☐" : "○"), inp,
        locked || q.options.length <= 2 ? null : h("button", { class: "link danger", onclick: () => { q.options.splice(k, 1); drawQuestions(); } }, "✕")));
    });
    if (!locked && q.options.length < 20) {
      box.append(h("button", { class: "link", onclick: () => { q.options.push(`옵션 ${q.options.length + 1}`); drawQuestions(); } }, "+ 선택지 추가"));
    }
    return box;
  }

  function payload() {
    const p = { title: title.value, description: desc.value, closes_at: kstInputToIso(closes.value) };
    if (!locked) {
      Object.assign(p, { questions: model.questions, opens_at: kstInputToIso(opens.value),
        min_results: +minRes.value, course_name: course.value, semester: semester.value, access_mode: access.value });
    }
    return p;
  }

  async function save() {
    if (!title.value.trim()) { toast("제목을 입력하세요", "error"); return null; }
    try {
      const saved = model.id ? await patch(`/api/surveys/${model.id}`, payload()) : await post("/api/surveys", payload());
      toast("저장했습니다", "success");
      if (!model.id) { go(`/surveys/edit/${saved.id}`); return null; }
      return saved;
    } catch (e) { errorToast(e); return null; }
  }

  const saveBtn = h("button", { class: "btn primary" }, locked ? "변경 저장" : "초안 저장");
  saveBtn.addEventListener("click", busy(saveBtn, async () => { const r = await save(); if (r) render(root, { id: r.id }); }));
  const previewBtn = h("button", { class: "btn", onclick: () => { preview = !preview; draw(); } }, "미리보기");
  const pubBtn = h("button", { class: "btn primary" }, "게시");
  pubBtn.addEventListener("click", busy(pubBtn, async () => {
    if (!(await confirmAction("설문 게시", "게시 후에는 문항을 수정할 수 없습니다(복제로 새 버전 생성). 게시할까요?", "게시"))) return;
    const r = await save();
    if (!r) return;
    try { await post(`/api/surveys/${r.id}/publish`); toast("게시했습니다", "success"); render(root, { id: r.id }); } catch (e) { errorToast(e); }
  }));
  const closeBtn = h("button", { class: "btn danger" }, "설문 종료");
  closeBtn.addEventListener("click", busy(closeBtn, async () => {
    if (!(await confirmAction("설문 종료", "더 이상 응답을 받지 않습니다. 종료할까요?", "종료", true))) return;
    try { await post(`/api/surveys/${model.id}/close`); render(root, { id: model.id }); } catch (e) { errorToast(e); }
  }));
  const dupBtn = h("button", { class: "btn" }, "복제(새 버전)");
  dupBtn.addEventListener("click", busy(dupBtn, async () => {
    try { const d = await post(`/api/surveys/${model.id}/duplicate`); go(`/surveys/edit/${d.id}`); } catch (e) { errorToast(e); }
  }));
  const linkBtn = h("button", { class: "btn", onclick: async () => {
    const url = surveyUrl(model);
    try { await navigator.clipboard.writeText(url); toast("링크를 복사했습니다", "success"); } catch { toast(url); }
  } }, "링크 복사");

  function draw() {
    if (preview) {
      body.replaceChildren(h("div", { class: "preview-banner" }, "미리보기 — 실제로 제출되지 않습니다"),
        renderForm({ title: title.value, description: desc.value, access_mode: access.value, questions: model.questions.map((q, i) => ({ ...q, id: q.id ?? `p${i}` })) },
          () => toast("미리보기에서는 제출되지 않습니다")));
      previewBtn.textContent = "편집으로";
      return;
    }
    previewBtn.textContent = "미리보기";
    drawQuestions();
    body.replaceChildren(
      h("div", { class: "panel survey-settings" }, title, desc,
        field("참여 방식", access, "로그인형도 답변 작성자는 결과에 표시되지 않습니다. 익명형은 쿠키 삭제·다른 기기로 다시 참여할 수 있습니다. 게시 후 방식은 변경할 수 없습니다."),
        h("div", { class: "grid-form" }, field("교과목", course), field("학기", semester),
          field("시작(한국 시간)", opens, "비우면 게시 즉시"), field("마감(한국 시간)", closes),
          field("결과 공개 최소 응답 수", minRes, "이보다 적으면 결과·원문을 숨겨 개인 식별을 막습니다"))),
      locked ? h("p", { class: "notice" }, "게시된 설문입니다. 문항을 바꾸려면 '복제(새 버전)'를 사용하세요. 기존 응답은 보호됩니다.") : null,
      qBox);
  }

  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, model.id ? "설문 편집" : "새 설문"), badge(STATUS_LABEL[s.status], s.status)),
    h("div", { class: "toolbar" }, saveBtn, previewBtn,
      s.status === "draft" && model.id ? pubBtn : null,
      s.status === "published" ? closeBtn : null,
      model.id ? dupBtn : null, model.id && s.status !== "draft" ? linkBtn : null,
      s.status === "published" ? h("button", { class: "btn", onclick: () => showSurveyQr(model) }, "QR 공유") : null,
      model.id && s.status !== "draft" ? h("a", { class: "btn", href: `#/surveys/results/${model.id}` }, "결과") : null),
    body);
  draw();
}
