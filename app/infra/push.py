"""Android Chrome Web Push; restricted endpoints, no credentials in logs."""
import base64
import json
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.core.errors import BadRequest
from app.infra.gmail import MailFailure, format_time


def decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def validate_keys(public, private):
    from app.config import ConfigError
    try:
        if len(decode(private)) != 32 or len(decode(public)) != 65:
            raise ValueError()
        key = ec.derive_private_key(int.from_bytes(decode(private), "big"), ec.SECP256R1())
        if key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint) != decode(public):
            raise ValueError()
    except Exception:
        raise ConfigError("휴대폰 알림 공개키와 비밀키가 올바른 한 쌍인지 확인하세요") from None


def validate_subscription(value):
    try:
        endpoint = value["endpoint"]
        url = urlsplit(endpoint)
        # Only Android Chrome's provider is supported. No user-controlled network hosts.
        if (len(endpoint) > 2048 or url.scheme != "https" or url.netloc != "fcm.googleapis.com"
                or not url.path.startswith(("/fcm/send/", "/wp/")) or url.query or url.fragment):
            raise ValueError()
        keys = value["keys"]
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decode(keys["p256dh"]))
        if len(decode(keys["auth"])) != 16:
            raise ValueError()
        return {"endpoint": endpoint, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}}
    except Exception:
        raise BadRequest("지원되는 Android Chrome 알림 정보인지 확인하세요") from None


class NoRedirectSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs["allow_redirects"] = False
        return super().request(*args, **kwargs)


class PushSender:
    def __init__(self, settings, session_factory):
        self.settings, self.session_factory = settings, session_factory

    def close(self):
        pass

    def send(self, row):
        from pywebpush import WebPushException, webpush
        from sqlalchemy import select

        from app.db import utcnow
        from app.models import AuthSession, PushSubscription, User
        with self.session_factory() as db:
            item = db.execute(select(PushSubscription, User).join(
                AuthSession, AuthSession.id == PushSubscription.session_id).join(User).where(
                PushSubscription.id == row.subscription_id, AuthSession.expires_at > utcnow(),
                User.is_active.is_(True), User.role.in_(("professor", "admin")),
                User.email == self.settings.push_professor_email)).first()
            if not item or row.recipient != self.settings.push_professor_email:
                raise MailFailure("skipped", "device_or_permission_revoked")
            subscription = validate_subscription(item[0].subscription)
        # Never include student name, notes, topic, or arbitrary URLs on the lock screen.
        payload = json.dumps({"title": "ClassBridge 상담 예약 알림",
                              "body": f"상담 예약이 변경되었습니다 · {format_time(row.payload['start'])}",
                              "tag": row.event_key, "url": "/#/bookings"}, ensure_ascii=False)
        try:
            with NoRedirectSession() as session:
                response = webpush(subscription_info=subscription, data=payload,
                    vapid_private_key=self.settings.push_private_key,
                    vapid_claims={"sub": "mailto:" + self.settings.push_contact_email},
                    ttl=300, timeout=15, requests_session=session)
            if response.status_code not in (200, 201, 202):
                raise MailFailure("failed", "push_rejected")
            return "accepted"  # Provider acceptance is not proof of delivery to a phone.
        except WebPushException as exc:
            code = exc.response.status_code if exc.response is not None else None
            if code in (404, 410):
                with self.session_factory() as db:
                    sub = db.get(PushSubscription, row.subscription_id)
                    if sub:
                        db.delete(sub)
                        db.commit()
                raise MailFailure("skipped", "push_subscription_expired") from None
            if code == 429:
                raise MailFailure("pending", "push_rate_limited") from None
            if code in (401, 403):
                raise MailFailure("reauth", "push_key_rejected") from None
            raise MailFailure("uncertain", "push_delivery_unknown") from None
        except requests.RequestException:
            raise MailFailure("uncertain", "push_delivery_unknown") from None
