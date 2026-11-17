// Deterministic Korean daytime input; never silently roll a date/year forward.
export function parseDate(value, today) {
  let text = value.trim().replace(/년|월/g, "-").replace(/일/g, "").replace(/[./\s]+/g, "-");
  if (/^\d{8}$/.test(text)) text = `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6)}`;
  if (/^\d{4}$/.test(text)) text = `${text.slice(0, 2)}-${text.slice(2)}`;
  const parts = text.split("-").filter(Boolean);
  if (parts.length === 2) parts.unshift(today.slice(0, 4));
  if (parts.length !== 3 || !parts.every(p => /^\d+$/.test(p)) || parts[0].length !== 4)
    throw new Error("날짜는 11월 20일 또는 2026-11-20처럼 입력해 주세요.");
  const [year, month, day] = parts.map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (year < 2000 || year > 2100 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day)
    throw new Error("실제로 존재하는 날짜를 입력해 주세요.");
  const result = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  if (result < today) throw new Error("이미 지난 날짜입니다. 연도와 날짜를 확인해 주세요.");
  return result;
}

export function parseTime(value) {
  let text = value.trim();
  const period = text.match(/^(오전|오후)/)?.[1];
  text = text.replace(/^(오전|오후)\s*/, "").replace(/시/g, ":").replace(/분/g, "").replace(/\s+/g, ":").replace(/:+/g, ":").replace(/:$/, "");
  if (/^\d{3,4}$/.test(text)) text = `${text.slice(0, -2)}:${text.slice(-2)}`;
  const match = text.match(/^(\d{1,2})(?::(\d{1,2}))?$/);
  if (!match) throw new Error("시간은 10 00, 10시, 오후 3:30처럼 입력해 주세요.");
  let hour = Number(match[1]);
  const minute = Number(match[2] || 0);
  if (period) {
    if (hour < 1 || hour > 12) throw new Error("오전·오후 표기는 1~12시로 입력해 주세요.");
    hour = hour % 12 + (period === "오후" ? 12 : 0);
  } else if (hour >= 1 && hour <= 6) hour += 12;
  if (minute > 59 || hour < 8 || hour > 18 || (hour === 18 && minute !== 0))
    throw new Error("상담 시간은 오전 8시부터 오후 6시까지 입력해 주세요. 7시는 오전·오후를 임의로 정하지 않습니다.");
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

// Only deterministic interpretation here. Future AI candidates must use the same
// preview/server validation, never bypass it or submit directly.
function normalizeSentence(value) {
  return value.normalize("NFKC").trim()
    .replace(/담주/g, "다음주").replace(/이번\s*주/g, "이번주").replace(/다음\s*주/g, "다음주")
    .replace(/([월화수목금토일])욜/g, "$1요일")
    .replace(/(오전|오후)\s+/g, "$1")
    .replace(/(열두|열한|열|아홉|여덟|일곱|여섯|다섯|네|세|두|한)\s*시/g, (_, n) =>
      `${({한:1,두:2,세:3,네:4,다섯:5,여섯:6,일곱:7,여덟:8,아홉:9,열:10,열한:11,열두:12})[n]}시`)
    .replace(/(\d{1,2})시\s*반/g, "$1:30");
}
function offsetDate(today, days) {
  const date = new Date(`${today}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function parseSchedule(value, today) {
  let text = normalizeSentence(value);
  if (!text || text.length > 300) throw new Error("일정은 300자 이내로 입력해 주세요.");
  if (/제외|빼고|취소|삭제|아니|말고/.test(text))
    throw new Error("제외·취소·정정 조건은 자동 적용하지 않습니다. 등록할 날짜와 시간만 다시 적거나 아래 항목을 직접 수정해 주세요.");
  let date;
  const absolute = text.match(/^(?:((?:\d{4}년\s*)?\d{1,2}월\s*\d{1,2}일)|((?:\d{4}[-/.])?\d{1,2}[/.]\d{1,2})|(\d{4}-\d{1,2}-\d{1,2}))/);
  const relative = text.match(/^(오늘|내일|모레)/);
  const weekday = text.match(/^(이번주|다음주)\s*([월화수목금토일])(?:요일)?/);
  if (absolute) {
    date = parseDate(absolute[0], today); text = text.slice(absolute[0].length);
    const dayLabel = text.match(/^\s*\(?([월화수목금토일])요일\)?/);
    if (dayLabel) {
      if ("일월화수목금토"[new Date(`${date}T00:00:00Z`).getUTCDay()] !== dayLabel[1])
        throw new Error("입력한 날짜와 요일이 다릅니다. 어느 쪽이 맞는지 확인해 주세요.");
      text = text.slice(dayLabel[0].length);
    }
  } else if (relative) {
    date = offsetDate(today, {오늘:0,내일:1,모레:2}[relative[1]]); text = text.slice(relative[0].length);
  } else if (weekday) {
    const day = new Date(`${today}T00:00:00Z`).getUTCDay();
    date = parseDate(offsetDate(today, -((day + 6) % 7) + "월화수목금토일".indexOf(weekday[2]) + (weekday[1] === "다음주" ? 7 : 0)), today);
    text = text.slice(weekday[0].length);
  } else {
    throw new Error("날짜를 확인해 주세요. 예: 내일, 다음주 화요일, 11월 20일. 요일만 적으면 어느 주인지 알 수 없습니다.");
  }
  // Metadata is optional. Leave existing form fields unchanged when absent.
  const extras = {};
  const consume = (pattern, key, min, max) => {
    const matches = [...text.matchAll(pattern)];
    if (matches.length > 1) throw new Error("같은 조건이 여러 번 있습니다. 하나만 남겨 주세요.");
    if (!matches.length) return;
    const number = Number(matches[0][1]);
    if (number < min || number > max) throw new Error(`${key === "durationMinutes" ? "1회 시간" : key === "breakMinutes" ? "휴식" : "반복 주수"} 범위를 확인해 주세요 (${min}~${max}).`);
    extras[key] = number; text = text.replace(matches[0][0], " ");
  };
  consume(/(?:휴식|쉬는시간)\s*(\d+)\s*분/g, "breakMinutes", 0, 120);
  consume(/(\d+)\s*분\s*씩/g, "durationMinutes", 5, 240);
  consume(/(?:총\s*)?(\d+)\s*주\s*(?:동안|간)?/g, "repeatWeeks", 1, 26);
  if (/매주/.test(text)) {
    if (!extras.repeatWeeks) throw new Error("매주 몇 주 동안 등록할까요? 예: 매주 4주. 이번 날짜를 포함한 총 주수입니다.");
    text = text.replace(/매주/g, " ");
  } else if (extras.repeatWeeks) throw new Error("반복 등록이면 ‘매주’를 함께 적어 주세요.");
  const location = text.match(/장소\s*[:：]?\s*([\w가-힣-]+)(?:\s|$)/);
  if (location) { extras.location = location[1]; text = text.replace(location[0], " "); }
  text = text.replace(/(?:상담|등록)(?:해\s*줘|해주세요|해줘요)?/g, " ").trim().replace(/^[,:\s]+|[,.!\s]+$/g, "");
  const range = text.match(/^(.+?)\s*(?:~|～|–|부터|-)\s*(.+?)(?:까지)?$/);
  if (!range) throw new Error("시작과 종료 시간을 함께 적어 주세요. 예: 오후 두시부터 네시반까지.");
  const start = parseTime(range[1]), end = parseTime(range[2]);
  if (end <= start) throw new Error("종료 시간은 시작 시간보다 늦어야 합니다. 다음 날로 자동 변경하지 않습니다.");
  return { date, start, end, ...extras };
}

export function timeLabel(value) {
  const [hour, minute] = value.split(":").map(Number);
  return `${hour < 12 ? "오전" : "오후"} ${hour % 12 || 12}:${String(minute).padStart(2, "0")}`;
}
