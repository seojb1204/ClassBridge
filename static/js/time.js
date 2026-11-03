// 한국 시간 표시 유틸. 서버는 UTC ISO 문자열을 준다.
const TZ = "Asia/Seoul";
const fmt = (opts) => new Intl.DateTimeFormat("ko-KR", { timeZone: TZ, ...opts });
const partsFmt = fmt({ year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  hourCycle: "h23", weekday: "short" });

export function kstParts(iso) {
  const p = Object.fromEntries(partsFmt.formatToParts(new Date(iso)).map((x) => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, hour: +p.hour, minute: +p.minute, time: `${p.hour}:${p.minute}`,
    weekday: p.weekday };
}

export const fmtDateTime = (iso) => fmt({ month: "long", day: "numeric", weekday: "short", hour: "2-digit",
  minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
export const fmtTime = (iso) => kstParts(iso).time;
export const fmtDate = (isoDate) => fmt({ month: "long", day: "numeric", weekday: "short" })
  .format(new Date(`${isoDate}T12:00:00+09:00`));

export function todayKst() { return kstParts(new Date().toISOString()).date; }

export function addDays(isoDate, n) {
  const d = new Date(`${isoDate}T12:00:00+09:00`);
  d.setUTCDate(d.getUTCDate() + n);
  return kstParts(d.toISOString()).date;
}

export function mondayOf(isoDate) {
  const wd = new Date(`${isoDate}T12:00:00+09:00`).getUTCDay(); // 0=일
  return addDays(isoDate, wd === 0 ? -6 : 1 - wd);
}

export function kstInputToIso(localValue) {
  // <input type=datetime-local> 값(한국 시간)을 UTC ISO로
  return localValue ? new Date(`${localValue}:00+09:00`).toISOString() : null;
}

export function isoToKstInput(iso) {
  if (!iso) return "";
  const p = kstParts(iso);
  return `${p.date}T${p.time}`;
}
