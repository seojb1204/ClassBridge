"""Staff push preferences and scheduled messages. Re-read the schedule immediately before sending."""
from collections import defaultdict
from datetime import datetime, time, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models import AppSetting, AuthSession, Booking, Notification, PushSubscription, Slot, User
from app.timeutil import kst_to_utc, to_kst

EMAIL_PAUSED = "booking_email_paused"


class Preferences(BaseModel):
    daily: bool
    at: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    reminder: bool
    instant: bool
    names: bool


def preferences(user):
    default = user.role == "professor"
    return Preferences(**({"daily": default, "at": "10:00", "reminder": False, "instant": default, "names": True}
                          | (user.alert_preferences or {})))


def email_paused(db):
    setting = db.get(AppSetting, EMAIL_PAUSED)
    return bool(setting and setting.value)


def devices(now):
    return select(PushSubscription, User).join(AuthSession, AuthSession.id == PushSubscription.session_id).join(
        User, User.id == AuthSession.user_id).where(AuthSession.expires_at > now, User.is_active.is_(True),
                                                   User.role.in_(("professor", "admin")))


def schedule_rows(db, now):
    day = to_kst(now).date()
    return db.execute(select(Slot.start_at, Slot.end_at, Booking.applicant_name, User.name).select_from(Slot)
                      .join(Booking, Booking.slot_id == Slot.id).join(User, User.id == Booking.student_id)
                      .where(Booking.status == "booked", Slot.status == "open", Slot.end_at > now,
                             Slot.start_at >= kst_to_utc(day, time.min),
                             Slot.start_at < kst_to_utc(day + timedelta(days=1), time.min))
                      .order_by(Slot.start_at, Booking.id)).all()


def daily_due(pref, now):
    day = to_kst(now).date()
    return kst_to_utc(day, time.fromisoformat(pref.at)) if pref.daily and day.weekday() < 5 else None


GRACE = timedelta(minutes=3)


def enqueue_due(db, now):
    rows = None
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    for device, user in db.execute(devices(now)):
        pref = preferences(user)
        due = daily_due(pref, now)
        summary = due is not None and due <= now < due + GRACE
        if not summary and not pref.reminder:
            continue
        if rows is None:
            rows = schedule_rows(db, now)
        if not rows:
            continue
        jobs = []
        if summary:
            jobs.append(("daily", due, to_kst(now).date().isoformat()))
        if pref.reminder:
            for start in sorted({r.start_at for r in rows}):
                when = start - timedelta(minutes=30)
                if when != due and when <= now < when + GRACE:
                    jobs.append(("reminder", when, str(int(start.timestamp()))))
        for kind, when, key in jobs:
            stmt = insert(Notification).values(event_key=f"{kind}-{device.id}-{key}", chain_id=-int(when.timestamp()),
                booking_id=0, payload={"kind": kind, "due": when.isoformat()}, sender="", recipient=user.email,
                channel="push", subscription_id=device.id, next_attempt_at=now)
            db.execute(stmt.on_conflict_do_nothing(index_elements=[Notification.event_key]))
    db.commit()


def scheduled_message(db, payload, pref, now):
    when = datetime.fromisoformat(payload["due"])
    if not when <= now < when + GRACE:
        return None
    rows = schedule_rows(db, now)
    daily = payload["kind"] == "daily"
    upcoming = when + timedelta(minutes=30)
    if daily:
        if daily_due(pref, now) != when:
            return None
    elif not pref.reminder:
        return None
    groups = defaultdict(list)
    for start, _, applicant, account in rows:
        if daily or start == upcoming:
            groups[start].append(applicant or account)
    if not groups:
        return None
    day = to_kst(now)
    count = sum(map(len, groups.values()))
    weekday = "월화수목금토일"[day.weekday()]
    title = f"오늘 상담 {count}건 · {day.month}월 {day.day}일({weekday})" if daily else "30분 후 상담"
    lines = []
    for start, names in groups.items():
        k = to_kst(start)
        label = f"{'오전' if k.hour < 12 else '오후'} {k.hour % 12 or 12}시"
        if k.minute:
            label += f" {k.minute}분"
        people = ", ".join(names) if pref.names else f"{len(names)}명"
        lines.append(f"{label} · {people}" + (" · 30분 후" if daily and pref.reminder and start == upcoming else ""))
    body = "\n".join(lines)
    # Keep encrypted Web Push below the provider size limit; the full list opens in the app.
    if len(body.encode()) > 2400:
        body = body.encode()[:2300].decode(errors="ignore") + "… 앱에서 전체 일정 보기"
    return {"title": title, "body": body, "url": "/#/bookings/today"}
