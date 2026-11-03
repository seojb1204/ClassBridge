// 교수자·관리자: 예약 현황 · 완료/미참석 · 상담 기록 · 대리 예약 · 일정 조정
import { get, post, put } from "../api.js";
import { addDays, fmtDateTime, kstParts, todayKst } from "../time.js";
import {
  STATUS_LABEL, badge, busy, empty, errorToast, field, h, modal, mount, promptText, select, toast,
} from "../ui.js";

let filter = { start: null, days: 31, status: "booked" };

export async function render(root) {
  filter.start ||= addDays(todayKst(), -7);
  const q = new URLSearchParams({ start: filter.start, days: filter.days });
  if (filter.status) q.set("status", filter.status);
  const list = await get(`/api/bookings?${q}`);
  const start = h("input", { type: "date", value: filter.start });
  const status = select([["", "전체"], ["booked", "예약됨"], ["completed", "완료"], ["no_show", "미참석"],
    ["cancelled", "취소됨"]], filter.status);
  const apply = () => { filter = { ...filter, start: start.value, status: status.value }; render(root); };
  start.addEventListener("change", apply);
  status.addEventListener("change", apply);
  const newBtn = h("button", { class: "btn primary", onclick: () => bookForStudent(root) }, "학생 대신 예약");
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "예약 관리"), newBtn),
    h("div", { class: "filters" }, field("시작일", start), field("상태", status)),
    list.length ? h("div", { class: "table-wrap" }, table(root, list)) : empty("해당 조건의 예약이 없습니다."));
}

function table(root, list) {
  return h("table", { class: "table" },
    h("thead", {}, h("tr", {}, ["일시", "학생", "유형", "상담 내용", "상태", "작업"].map((t) => h("th", {}, t)))),
    h("tbody", {}, list.map((b) => h("tr", { dataset: { bookingId: b.id } },
      h("td", { "data-label": "일시" }, fmtDateTime(b.slot.start_at)),
      h("td", { "data-label": "학생" }, `${b.student_name} `, h("small", { class: "muted" }, b.student_email)),
      h("td", { "data-label": "유형" }, b.slot.kind === "group" ? "단체" : "개인"),
      h("td", { "data-label": "상담 내용" }, b.topic || "-"),
      h("td", { "data-label": "상태" }, badge(STATUS_LABEL[b.status], b.status)),
      h("td", { "data-label": "작업", class: "actions" }, actions(root, b))))));
}

function actions(root, b) {
  const started = new Date(b.slot.start_at) <= new Date();
  const out = [];
  const act = (label, fn, cls = "btn small") => {
    const btn = h("button", { class: cls }, label);
    btn.addEventListener("click", busy(btn, async () => {
      try { await fn(); await render(root); } catch (e) { errorToast(e); }
    }));
    out.push(btn);
  };
  if (["booked", "completed", "no_show"].includes(b.status) && started) {
    if (b.status !== "completed") act("완료", async () => { await post(`/api/bookings/${b.id}/outcome`, { outcome: "completed" }); toast("완료 처리", "success"); });
    if (b.status !== "no_show") act("미참석", async () => { await post(`/api/bookings/${b.id}/outcome`, { outcome: "no_show" }); toast("미참석 처리", "success"); });
  }
  if (b.status === "booked") {
    act("일정 조정", () => reschedule(b));
    act("취소", async () => {
      const reason = await promptText("예약 취소", "취소 사유 (학생에게 표시됨)", { required: true });
      if (reason === null) return;
      await post(`/api/bookings/${b.id}/cancel`, { reason });
      toast("취소했습니다", "success");
    }, "btn small danger");
  }
  act("상담 기록", async () => {
    const note = await promptText("상담 기록", "교수자·관리자만 볼 수 있습니다. 외부 AI로 전송되지 않습니다.",
      { multiline: true, value: b.professor_note });
    if (note === null) return;
    await put(`/api/bookings/${b.id}/note`, { note });
    toast("저장했습니다", "success");
  });
  act("이력", async () => {
    const ev = await get(`/api/bookings/${b.id}/history`);
    await modal("변경 이력", h("ul", { class: "plain" }, ev.map((e) => h("li", {}, `${fmtDateTime(e.at)} · ${e.action} ${e.detail}`))),
      [{ label: "닫기", value: null }]);
  });
  return out;
}

async function pickSlot(title) {
  const from = todayKst();
  const slots = (await get(`/api/slots?start=${from}&days=31`)).filter((s) => s.status === "open" && s.remaining > 0
    && new Date(s.start_at) > new Date());
  if (!slots.length) { toast("남은 자리가 있는 상담 시간이 없습니다", "error"); return null; }
  const sel = select(slots.map((s) => [s.id, `${kstParts(s.start_at).date} ${kstParts(s.start_at).time} (${s.kind === "group" ? `단체 ${s.remaining}석` : "개인"})`]));
  const reason = h("input", { type: "text", maxlength: 500, placeholder: "사유" });
  const r = await modal(title, h("div", {}, field("상담 시간", sel), field("사유", reason)), [
    { label: "취소", value: null }, { label: "확인", primary: true, handler: () => ({ slot: +sel.value, reason: reason.value }) },
  ]);
  return r;
}

async function reschedule(b) {
  const r = await pickSlot("일정 조정");
  if (!r) return;
  if (!r.reason.trim()) { toast("사유를 입력하세요", "error"); return; }
  await post(`/api/bookings/${b.id}/reschedule`, { new_slot_id: r.slot, reason: r.reason });
  toast("일정을 조정했습니다", "success");
}

async function bookForStudent(root) {
  try {
    const students = await get("/api/students");
    if (!students.length) { toast("등록된 학생이 없습니다", "error"); return; }
    const who = select(students.map((s) => [s.id, `${s.name} (${s.email})`]));
    const r1 = await modal("학생 선택", field("학생", who), [{ label: "취소", value: null }, { label: "다음", primary: true, handler: () => +who.value }]);
    if (!r1) return;
    const r2 = await pickSlot("상담 시간 선택");
    if (!r2) return;
    await post("/api/bookings", { slot_id: r2.slot, student_id: r1, topic: r2.reason });
    toast("예약했습니다", "success");
    await render(root);
  } catch (e) { errorToast(e); }
}
