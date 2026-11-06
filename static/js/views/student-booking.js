import { availableDaysPanel, loadAvailableDays } from "../components/available-days.js";
// 학생: 상담 시간표 보기 · 예약 · 변경
import { get, post } from "../api.js";
import { announcementPanel, loadAnnouncement } from "../components/announcement.js";
import { onLayoutChange, renderCalendar, weekNav } from "../components/week-calendar.js";
import { fmtDateTime, kstParts, mondayOf, todayKst } from "../time.js";
import { errorToast, field, h, modal, mount, select, toast } from "../ui.js";
import { state } from "../state.js";

let weekStart = null;
let selectedDay = null;
let detach = null;
let drawVersion = 0;
let mobileView = "list";

export async function render(root) {
  if (!weekStart) {
    weekStart = mondayOf(todayKst());
    selectedDay = todayKst();
    // On the first visit, show the earliest actually available appointment.
    const upcoming = await get(`/api/slots?start=${todayKst()}&days=30`);
    const first = upcoming.find((s) => s.bookable);
    if (first) {
      selectedDay = kstParts(first.start_at).date;
      weekStart = mondayOf(selectedDay);
    }
  }
  detach?.();
  detach = onLayoutChange(() => draw(root));
  await draw(root);
}

async function draw(root) {
  if (location.hash !== "#/booking") return;
  const version = ++drawVersion, path = location.hash;
  const [slots, mine, policy, announcement, availableDays] = await Promise.all([
    get(`/api/slots?start=${weekStart}&days=7`),
    get("/api/bookings/mine"),
    get("/api/booking-policy"),
    loadAnnouncement(), loadAvailableDays(),
  ]);
  if (version !== drawVersion || location.hash !== path) return;
  const active = mine.find((b) => b.status === "booked");
  mount(root,
    h("div", { class: "page-head" }, h("h1", {}, "상담 예약")),
    availableDaysPanel(availableDays, (day) => { weekStart = mondayOf(day); selectedDay = day; draw(root); }),
    announcementPanel(announcement),
    h("details", { class: "booking-guide" }, h("summary", {}, "예약 방법·마감 시간"),
      h("p", {}, `‘예약 가능’ 시간을 눌러 예약하세요. 앞으로 ${policy.booking_window_days}일 이내 상담을 ` +
        `시작 ${policy.booking_deadline_hours}시간 전까지 예약할 수 있습니다. 취소·변경은 시작 ${policy.cancel_deadline_hours}시간 전까지 가능합니다.`)),
    active ? h("div", { class: "notice", role: "status" }, "예약 확정: ",
      h("strong", {}, fmtDateTime(active.slot.start_at)),
      " · 내 예약을 누르면 취소할 수 있고, 다른 가능 시간을 누르면 변경할 수 있습니다.",
      h("a", { class: "btn small", href: "#/my-bookings" }, "예약 내역")) : null,
    legend(),
    weekNav(weekStart, (w) => { weekStart = w; selectedDay = w; draw(root); }),
    renderCalendar({ weekStart, slots, selectedDay, mobileView,
      onViewChange: (mode) => { mobileView = mode; draw(root); },
      onDay: (d) => { selectedDay = d; draw(root); },
      onSlot: (s) => openSlot(root, s, active, policy) }),
  );
}

function legend() {
  return h("div", { class: "legend" },
    h("span", { class: "lg open" }, "예약 가능"), h("span", { class: "lg mine" }, "내 예약"),
    h("span", { class: "lg closed" }, "마감·불가"));
}

async function openSlot(root, s, active, policy) {
  if (s.mine) {
    const result = await modal("내 상담 예약", h("div", { class: "booking-detail" },
      h("p", {}, h("strong", {}, fmtDateTime(s.start_at))),
      h("p", { class: "muted" }, "예약 확정 · " + (s.kind === "group" ? "단체 상담" : "개인 상담")),
      h("p", {}, `예약 취소는 상담 시작 ${policy.cancel_deadline_hours}시간 전까지 가능합니다. 이 예약을 취소하시겠습니까?`)), [
      { label: "돌아가기", value: null },
      { label: "예약 취소", danger: true, handler: async () => {
        try {
          await post(`/api/bookings/${active.id}/cancel`, {});
          return true;
        } catch (e) { errorToast(e); return false; }
      } },
    ]);
    if (result === true) {
      toast("예약을 취소했습니다.", "success");
      await draw(root);
    }
    return;
  }
  if (!s.bookable) { toast(s.reason || "예약할 수 없는 시간입니다", "error"); return; }
  const topic = h("textarea", { rows: 3, maxlength: 500, placeholder: "상담 받고 싶은 내용 (선택)" });
  const applicantName = h("input", { type: "text", maxlength: 100, placeholder: "학생 이름",
    value: state.me?.name || "" });
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
        field("상담 방식", consultationMode), field("상담 내용", topic),
        h("p", { class: "muted" }, "학업·진로·취업 상담에 필요한 내용만 입력해 주세요. 건강·심리 상태 등 민감한 개인정보는 입력하지 마세요.")));
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
        if (e.code === "slot_full") toast("다른 학생이 먼저 예약했습니다. 가능한 시간을 다시 선택해 주세요.", "error");
        else errorToast(e);
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

