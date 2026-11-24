import { get, post, clearCalendarCache } from "../api.js";
import { todayKst, kstInputToIso } from "../time.js";
import { busy, errorToast, field, h, select, toast } from "../ui.js";

// Account linkage is optional; an unlinked reservation always requires a name.
export function staffBookingForm(onSaved = () => {}, seed = null) {
  const name = h("input", {type: "text", required: true, maxlength: 100, autocomplete: "off"});
  const who = select([["", "연결하지 않음"]], "");
  const hint = h("p", {class: "hint"}, "계정 미연결 예약은 학생의 내 예약에 표시되지 않아요.");
  const date = h("input", {type: "date", required: true, value: seed?.date || todayKst()});
  const start = h("input", {type: "time", required: true, value: seed?.start || "14:00"});
  const end = h("input", {type: "time", required: true, value: seed?.end || "14:30"});
  const place = h("input", {type: "text", maxlength: 200, value: "", placeholder: "예: 상담실"});
  const topic = h("textarea", {rows: 2, maxlength: 500});
  const save = h("button", {type: "submit", class: "btn primary"}, "예약 등록");
  const accountStatus = h("small", {class: "hint", role: "status"});
  const form = h("form", {class: "staff-booking-form"},
    field("학생 이름 *", name), field("학생 계정 연결 (선택)", who), accountStatus,
    field("날짜", date), h("div", {class: "booking-time-fields"}, field("시작", start), field("종료", end)),
    field("장소 (선택)", place),
    h("details", {}, h("summary", {}, "상담 주제 (선택)"), field("상담 주제", topic)), hint, save);
  let students = [];
  get("/api/students").then(rows => {
    students = rows;
    rows.forEach(s => who.append(h("option", {value: s.id}, `${s.name} (${s.email})`)));
  }).catch(() => { accountStatus.textContent = "계정 목록을 불러오지 못했습니다. 이름만 입력해 등록할 수 있습니다."; });
  who.onchange = () => {
    const student = students.find(s => String(s.id) === who.value);
    if (student) name.value = student.name;
    hint.textContent = student ? "연결한 학생의 내 예약에 표시됩니다." : "계정 미연결 예약은 학생의 내 예약에 표시되지 않아요.";
  };
  form.addEventListener("submit", busy(save, async event => {
    event.preventDefault();
    if (!name.value.trim()) { name.focus(); toast("학생 이름을 입력하세요", "error"); return; }
    try {
      const result = await post("/api/bookings", {student_id: who.value ? Number(who.value) : null,
        applicant_name: name.value.trim(), start_at: kstInputToIso(`${date.value}T${start.value}`),
        end_at: kstInputToIso(`${date.value}T${end.value}`), location: place.value, topic: topic.value});
      clearCalendarCache();
      toast("예약을 등록했습니다", "success");
      await onSaved(result);
    } catch (error) { errorToast(error); }
  }));
  return form;
}
