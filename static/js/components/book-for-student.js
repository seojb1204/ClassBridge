import { get, post, clearCalendarCache } from "../api.js";
import { todayKst, kstParts } from "../time.js";
import { errorToast, field, h, modal, select, toast } from "../ui.js";

async function pickSlot(title, noteLabel = "사유 (선택)") {
  const from = todayKst();
  const slots = (await get(`/api/slots?start=${from}&days=31`)).filter((s) => s.status === "open" && s.remaining > 0
    && new Date(s.start_at) > new Date());
  if (!slots.length) { toast("남은 자리가 있는 상담 시간이 없습니다", "error"); return null; }
  const sel = select(slots.map((s) => [s.id, `${kstParts(s.start_at).date} ${kstParts(s.start_at).time} (${s.kind === "group" ? `단체 ${s.remaining}석` : "개인"})`]));
  const reason = h("input", { type: "text", maxlength: 500 });
  const r = await modal(title, h("div", {}, field("상담 시간", sel), field(noteLabel, reason)), [
    { label: "취소", value: null }, { label: "확인", primary: true, handler: () => ({ slot: +sel.value, reason: reason.value }) },
  ]);
  return r;
}

export async function bookForStudent(onSaved = () => {}) {
  try {
    const students = await get("/api/students");
    if (!students.length) { toast("등록된 학생이 없습니다", "error"); return; }
    const who = select(students.map((s) => [s.id, `${s.name} (${s.email})`]));
    const r1 = await modal("학생 선택", field("학생", who), [{ label: "취소", value: null }, { label: "다음", primary: true, handler: () => +who.value }]);
    if (!r1) return;
    const r2 = await pickSlot("상담 시간 선택", "상담 주제 (선택)");
    if (!r2) return;
    await post("/api/bookings", { slot_id: r2.slot, student_id: r1, topic: r2.reason });
    clearCalendarCache();
    toast("예약했습니다", "success");
    await onSaved();
  } catch (e) { errorToast(e); }
}


