"""환경변수 기반 설정. 운영(production)에서 위험한 조합은 시작 시점에 거부한다."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


class ConfigError(RuntimeError):
    pass


@dataclass
class Settings:
    env: str = "development"  # development | test | production
    database_url: str = "sqlite:///./classbridge_dev.db"
    secret_key: str = "dev-only-insecure-secret"
    base_url: str = "http://localhost:8000"

    google_client_id: str = ""
    google_client_secret: str = ""

    gmail_notifications_enabled: bool = False
    gmail_client_id: str = ""
    gmail_client_secret: str = field(default="", repr=False)
    gmail_refresh_token: str = field(default="", repr=False)
    gmail_sender_email: str = ""
    gmail_professor_email: str = ""
    push_enabled: bool = False
    push_public_key: str = ""
    push_private_key: str = field(default="", repr=False)
    push_professor_email: str = ""
    push_contact_email: str = ""

    # 최초 역할 부여용 허용 목록 (계정 최초 생성 시에만 적용)
    admin_emails: list[str] = field(default_factory=list)
    professor_emails: list[str] = field(default_factory=list)
    # 비어 있으면 모든 Google 계정 허용, 값이 있으면 해당 도메인만 학생 가입 허용
    allowed_email_domains: list[str] = field(default_factory=list)

    # Staging mode: any Google account not explicitly approved is denied access.
    # No change to the confirmed personal-Gmail policy for real deployment.
    staging_mode: bool = False
    staging_allowed_emails: list[str] = field(default_factory=list)

    dev_login_enabled: bool = False

    session_ttl_hours: int = 12
    cookie_secure: bool = False
    public_notice_enabled: bool = False
    operator_name: str = ""
    operator_affiliation: str = ""
    support_email: str = ""

    feature_surveys: bool = True
    feature_suggestions: bool = True
    ai_mode: str = "demo"  # disabled | demo | external
    ai_api_key: str = ""
    ai_model: str = "claude-haiku-5-5"

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def validate(self) -> None:
        if self.push_enabled:
            if not all((self.push_public_key, self.push_private_key,
                        self.push_professor_email, self.push_contact_email)):
                raise ConfigError("휴대폰 알림 키·수신 교수자·운영 연락처 설정이 필요합니다")
            from app.infra.push import validate_keys
            validate_keys(self.push_public_key, self.push_private_key)
            import re
            for address in (self.push_professor_email, self.push_contact_email):
                if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", address):
                    raise ConfigError("휴대폰 알림 수신·연락처는 각각 하나의 이메일이어야 합니다")
        if self.gmail_notifications_enabled:
            import re
            from urllib.parse import urlsplit
            if not all((self.gmail_client_id, self.gmail_client_secret, self.gmail_refresh_token)):
                raise ConfigError("Gmail 발송용 인증 설정이 필요합니다 (값은 로그에 표시하지 않습니다)")
            for address in (self.gmail_sender_email, self.gmail_professor_email):
                if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", address):
                    raise ConfigError("Gmail 발신·수신 주소는 각각 하나의 이메일이어야 합니다")
            url = urlsplit(self.base_url)
            if not url.netloc or url.username or url.password or url.query or url.fragment:
                raise ConfigError("Gmail 확인 링크 BASE_URL을 확인하세요")
            if self.is_production and url.scheme != "https":
                raise ConfigError("운영 Gmail 확인 링크에는 HTTPS가 필요합니다")
            if self.gmail_client_id == self.google_client_id:
                raise ConfigError("로그인용과 발송용 OAuth 클라이언트를 분리하세요")
        if self.public_notice_enabled and (not self.operator_name.strip()
                or "@" not in self.support_email or any(c in self.support_email for c in "\r\n<>")):
            raise ConfigError("Public notice requires OPERATOR_NAME and SUPPORT_EMAIL")
        if self.ai_mode not in {"disabled", "demo", "external"}:
            raise ConfigError("AI_MODE must be disabled|demo|external")
        if self.staging_mode:
            if not self.staging_allowed_emails:
                raise ConfigError("STAGING_ALLOWED_EMAILS must contain test accounts when STAGING_MODE=true")
            required = set(self.admin_emails + self.professor_emails)
            if not required.issubset(self.staging_allowed_emails):
                raise ConfigError("Staging allowlist must include all initial admin/professor emails")
        if not self.is_production:
            return
        problems = []
        if self.dev_login_enabled:
            problems.append("DEV_LOGIN_ENABLED는 운영 환경에서 사용할 수 없습니다")
        if self.secret_key.startswith("dev-") or len(self.secret_key) < 32:
            problems.append("SECRET_KEY는 32자 이상의 임의 값이어야 합니다")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE=true 가 필요합니다 (HTTPS)")
        if self.database_url.startswith("sqlite"):
            problems.append("운영 환경은 PostgreSQL DATABASE_URL이 필요합니다")
        oauth_configured = bool(self.google_client_id and self.google_client_secret)
        # An empty OAuth configuration is permitted ONLY for the locked-down
        # staging bootstrap. In this state Google login is unavailable.
        if not oauth_configured:
            if not (self.staging_mode and not self.google_client_id and not self.google_client_secret):
                problems.append("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET가 필요합니다")
        if not self.admin_emails:
            problems.append("ADMIN_EMAILS에 최초 관리자 이메일이 필요합니다")
        if self.ai_mode == "external" and not self.ai_api_key:
            problems.append("AI_MODE=external 에는 AI_API_KEY가 필요합니다")
        if problems:
            raise ConfigError("; ".join(problems))


def load_settings() -> Settings:
    env = os.getenv("APP_ENV", "development")
    prod = env == "production"
    s = Settings(
        env=env,
        database_url=os.getenv("DATABASE_URL", Settings.database_url),
        secret_key=os.getenv("SECRET_KEY", Settings.secret_key),
        base_url=os.getenv("BASE_URL", Settings.base_url).rstrip("/"),
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
        gmail_notifications_enabled=_bool("GMAIL_NOTIFICATIONS_ENABLED", False),
        push_enabled=_bool("PUSH_ENABLED", False),
        push_public_key=os.getenv("PUSH_PUBLIC_KEY", ""),
        push_private_key=os.getenv("PUSH_PRIVATE_KEY", ""),
        push_professor_email=os.getenv("PUSH_PROFESSOR_EMAIL", "").strip().lower(),
        push_contact_email=os.getenv("PUSH_CONTACT_EMAIL", "").strip().lower(),
        gmail_client_id=os.getenv("GMAIL_CLIENT_ID", ""),
        gmail_client_secret=os.getenv("GMAIL_CLIENT_SECRET", ""),
        gmail_refresh_token=os.getenv("GMAIL_REFRESH_TOKEN", ""),
        gmail_sender_email=os.getenv("GMAIL_SENDER_EMAIL", "").strip().lower(),
        gmail_professor_email=os.getenv("GMAIL_PROFESSOR_EMAIL", "").strip().lower(),
        admin_emails=_list("ADMIN_EMAILS"),
        professor_emails=_list("PROFESSOR_EMAILS"),
        allowed_email_domains=_list("ALLOWED_EMAIL_DOMAINS"),
        staging_mode=_bool("STAGING_MODE", False),
        staging_allowed_emails=_list("STAGING_ALLOWED_EMAILS"),
        dev_login_enabled=_bool("DEV_LOGIN_ENABLED", env in {"development", "test"}),
        session_ttl_hours=int(os.getenv("SESSION_TTL_HOURS", "12")),
        cookie_secure=_bool("COOKIE_SECURE", prod),
        public_notice_enabled=_bool("PUBLIC_NOTICE_ENABLED", False),
        operator_name=os.getenv("OPERATOR_NAME", "").strip(),
        operator_affiliation=os.getenv("OPERATOR_AFFILIATION", "").strip(),
        support_email=os.getenv("SUPPORT_EMAIL", "").strip(),
        # 익명 기능은 운영에서 보안 검토 후 명시적으로 켜야 한다
        feature_surveys=_bool("FEATURE_SURVEYS", not prod),
        feature_suggestions=_bool("FEATURE_SUGGESTIONS", not prod),
        ai_mode=os.getenv("AI_MODE", "disabled" if prod else "demo"),
        ai_api_key=os.getenv("AI_API_KEY", ""),
        ai_model=os.getenv("AI_MODEL", Settings.ai_model),
    )
    s.validate()
    return s
