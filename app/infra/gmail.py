"""Send-only Gmail adapter. Never log HTTP bodies, headers or credentials."""
import base64
import time
from email.message import EmailMessage
from email.policy import SMTP
from urllib.parse import quote

import httpx

from app.timeutil import KST

SCOPE = "https://www.googleapis.com/auth/gmail.send"


class MailFailure(Exception):
    def __init__(self, state: str, code: str):
        self.state, self.code = state, code
        super().__init__(code)


def format_time(value):
    from datetime import datetime
    return datetime.fromisoformat(value).astimezone(KST).strftime("%Y-%m-%d %H:%M")


def message_for(row):
    p = row.payload
    labels = {"created": "예약 신청", "changed": "예약 변경", "cancelled": "예약 취소",
              "slot_changed": "상담 정보 변경"}
    label = labels[p["kind"]]
    msg = EmailMessage(policy=SMTP)
    msg["From"], msg["To"] = row.sender, row.recipient
    msg["Subject"] = f"[ClassBridge] {label} #{row.booking_id}"
    # Stable Message-ID aids human investigation, but is NOT Gmail idempotency.
    msg["Message-ID"] = f"<classbridge-{row.event_key}@{row.sender.split('@')[1]}>"
    lines = [label, f"학생 이름: {p['student_name']}", f"예약번호: #{row.booking_id}",
             f"상담: {format_time(p['start'])} ~ {format_time(p['end'])} (한국시간)"]
    if "old_id" in p:
        lines += [f"변경 전 예약번호: #{p['old_id']}",
                  f"변경 전: {format_time(p['old_start'])} ~ {format_time(p['old_end'])} (한국시간)"]
    lines += ["자세한 내용은 로그인 후 예약 관리에서 확인하세요.", p["url"],
              "학생 이름은 신청서에 입력된 값이며 별도로 신원을 인증한 정보가 아닙니다."]
    msg.set_content("\n".join(lines))
    return msg


class GmailSender:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.client = httpx.Client(timeout=httpx.Timeout(15, connect=5), transport=transport,
                                   follow_redirects=False)
        self.token = ""
        self.expires = 0.0

    def close(self):
        self.client.close()

    def refresh(self):
        s = self.settings
        try:
            r = self.client.post("https://oauth2.googleapis.com/token", data={
                "client_id": s.gmail_client_id, "client_secret": s.gmail_client_secret,
                "refresh_token": s.gmail_refresh_token, "grant_type": "refresh_token"})
        except httpx.HTTPError:
            raise MailFailure("pending", "token_network") from None
        if r.status_code == 429 or r.status_code >= 500:
            raise MailFailure("pending", "token_temporary")
        if r.status_code != 200:
            raise MailFailure("reauth", "token_rejected")
        try:
            data = r.json()
            # Fail closed if the provider cannot attest the exact send-only grant.
            if set(data.get("scope", "").split()) != {SCOPE}:
                raise MailFailure("reauth", "scope_unverified")
            token, ttl = data["access_token"], int(data["expires_in"])
            if not isinstance(token, str) or not token or ttl <= 0:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise MailFailure("reauth", "token_response_invalid") from None
        self.token, self.expires = token, time.monotonic() + max(0, ttl - 60)

    def send(self, row):
        if row.sender != self.settings.gmail_sender_email or row.recipient != self.settings.gmail_professor_email:
            raise MailFailure("failed", "recipient_config_changed")
        if not self.token or time.monotonic() >= self.expires:
            self.refresh()
        raw = base64.urlsafe_b64encode(message_for(row).as_bytes()).decode("ascii")
        # Explicit userId binds delivery to the approved sending account, not an arbitrary 'me'.
        url = f"https://gmail.googleapis.com/gmail/v1/users/{quote(row.sender, safe='')}/messages/send"
        for attempt in range(2):
            try:
                r = self.client.post(url, headers={"Authorization": f"Bearer {self.token}"}, json={"raw": raw})
            except httpx.HTTPError:
                raise MailFailure("uncertain", "send_network_unknown") from None
            if r.status_code == 401 and attempt == 0:
                self.token = ""
                self.refresh()
                continue
            break
        if r.status_code == 200:
            try:
                identifier = r.json()["id"]
                if not isinstance(identifier, str) or not identifier or len(identifier) > 100:
                    raise ValueError()
                return identifier
            except (ValueError, KeyError, TypeError):
                raise MailFailure("uncertain", "send_response_unknown") from None
        if r.status_code == 429:
            raise MailFailure("pending", "rate_limited")
        if r.status_code >= 500:
            raise MailFailure("uncertain", "send_server_unknown")
        if r.status_code == 403:
            try:
                reasons = {e.get("reason") for e in r.json().get("error", {}).get("errors", [])}
            except (ValueError, TypeError, AttributeError):
                reasons = set()
            if reasons & {"rateLimitExceeded", "userRateLimitExceeded"}:
                raise MailFailure("pending", "rate_limited")
            if "dailyLimitExceeded" in reasons:
                raise MailFailure("failed", "daily_quota_exceeded")
        if r.status_code in (401, 403):
            raise MailFailure("reauth", "send_access_rejected")
        raise MailFailure("failed", "send_rejected")
