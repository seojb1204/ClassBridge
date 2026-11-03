// 학생: 상담 시간표 보기 · 예약 · 변경
import { get, post } from "../api.js";
import { onLayoutChange, renderCalendar, weekNav } from "../components/week-calendar.js";
import { fmtDateTime, mondayOf, todayKst } from "../time.js";
import { errorToast, field, h, modal, mount, select, toast } from "../ui.js";

let weekStart = null;
let selectedDay = null;
let detach = null;

export async function render(root) {
  weekStart ||= mondayOf(todayKst());
  selectedDay ||= todayKst();
  detach?.();
  detach = onLayoutChange(() => draw(root));
  await draw(root);
}

async function draw(root) {
  const [slots, mine] = await Promise.all([
    get(`/api/slots?start=${weekStart}&days=7`),
    get("/api/bookings/mine"),
  ]);
  const active = mine.find((b) => b.status === "booked");
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "상담 예약"),
      h("p", { class: "muted" }, "강조된 시간을 눌러 예약하세요. 예약은 1인 1건, 취소·변경은 상담 시작 3시간 전까지 가능합니다.")),
    active ? h("div", { class: "notice" }, "현재 예약: ", h("strong", {}, fmtDateTime(active.slot.start_at)),
      " · 다른 시간을 누르면 예약을 변경할 수 있습니다.") : null,
    legend(),
    weekNav(weekStart, (w) => { weekStart = w; selectedDay = w; draw(root); }),
    renderCalendar({ weekStart, slots, selectedDay, onDay: (d) => { selectedDay = d; draw(root); },
      onSlot: (s) => openSlot(root, s, active) }),
  );
}

function legend() {
  return h("div", { class: "legend" },
    h("span", { class: "lg open" }, "예약 가능"), h("span", { class: "lg mine" }, "내 예약"),
    h("span", { class: "lg closed" }, "마감·불가"));
}

async function openSlot(root, s, active) {
  if (s.mine) {
    toast("이미 예약한 시간입니다. '내 예약'에서 취소할 수 있습니다.");
    return;
  }
  if (!s.bookable) { toast(s.reason || "예약할 수 없는 시간입니다", "error"); return; }
  const topic = h("textarea", { rows: 3, maxlength: 500, placeholder: "상담 받고 싶은 내용 (선택)" });
  const applicantName = h("input", { type: "text", maxlength: 100, placeholder: "학생 이름" });
  const studentNumber = h("input", { type: "text", maxlength: 30, placeholder: "학번 (별도 확인하지 않음)" });
  const grade = select([["", "선택 안 함"], ["1", "1학년"], ["2", "2학년"], ["3", "3학년"], ["4", "4학년"]]);
  const consultationType = select([["career", "진로"], ["employment", "취업"], ["academics", "학업"],
    ["campus", "학교생활"], ["other", "기타"]]);
  const consultationMode = select([["in_person", "대면"], ["online", "온라인"]]);
  const info = h("div", {},
    h("p", {}, h("strong", {}, fmtDateTime(s.start_at)), ` (${s.kind === "group" ? `단체 · 남은 자리 ${s.remaining}` : "개인 상담"})`),
    s.location ? h("p", { class: "muted" }, `장소: ${s.location}`) : null,
    s.note ? h("p", { class: "muted" }, s.note) : null,
    active ? h("p", { class: "warn" }, `기존 예약(${fmtDateTime(active.slot.start_at)})이 이 시간으로 변경됩니다.`)
      : h("div", {}, field("이름", applicantName), field("학번", studentNumber),
        field("학년", grade), field("상담 유형", consultationType),
        field("상담 방식", consultationMode), field("상담 내용", topic)));
  const result = await modal(active ? "예약 변경" : "상담 예약", info, [
    { label: "닫기", value: null },
    { label: active ? "이 시간으로 변경" : "예약하기", primary: true, handler: async () => {
      try {
        if (active) await post(`/api/bookings/${active.id}/reschedule`, { new_slot_id: s.id });
        else await post("/api/bookings", {
          slot_id: s.id, topic: topic.value, applicant_name: applicantName.value,
          student_number: studentNumber.value, grade: grade.value ? +grade.value : null,
          consultation_type: consultationType.value, consultation_mode: consultationMode.value,
        });
        return true;
      } catch (e) {
        errorToast(e);
        if (e.code === "slot_full" || e.status === 0) { await draw(root); return null; }
        return false;
      }
    } },
  ]);
  if (result === true) {
    toast(active ? "예약이 변경되었습니다." : "예약이 완료되었습니다.", "success");
    await draw(root);
  }
}

