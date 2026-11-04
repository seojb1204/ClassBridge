// Client-side calendar export. No booking details are sent to external services.
function utcIcs(iso) {
  return new Date(iso).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function escapeValue(value) {
  return String(value || "").replace(/\\/g, "\\\\").replace(/\r?\n/g, "\\n")
    .replace(/,/g, "\\,").replace(/;/g, "\\;");
}

export function downloadConsultationIcs(booking) {
  const start = utcIcs(booking.slot.start_at);
  const end = utcIcs(booking.slot.end_at);
  const content = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//ClassBridge//Consultation//KO",
    "BEGIN:VEVENT",
    `UID:booking-${booking.id}@classbridge`,
    `DTSTAMP:${utcIcs(new Date().toISOString())}`,
    `DTSTART:${start}`,
    `DTEND:${end}`,
    "SUMMARY:ClassBridge 상담",
    `LOCATION:${escapeValue(booking.slot.location)}`,
    "END:VEVENT",
    "END:VCALENDAR",
    "",
  ].join("\r\n");
  const blob = new Blob([content], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `classbridge-booking-${booking.id}.ics`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
