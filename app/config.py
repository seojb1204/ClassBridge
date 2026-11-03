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

    # 최초 역할 부여용 허용 목록 (계정 최초 생성 시에만 적용)
    admin_emails: list[str] = field(default_factory=list)
    professor_emails: list[str] = field(default_factory=list)
    # 비어 있으면 모든 Google 계정 허용, 값이 있으면 해당 도메인만 학생 가입 허용
    allowed_email_domains: list[str] = field(default_factory=list)

    dev_login_enabled: bool = False

    session_ttl_hours: int = 12
    cookie_secure: bool = False

    feature_surveys: bool = True
    feature_suggestions: bool = True
    ai_mode: str = "demo"  # disabled | demo | external
    ai_api_key: str = ""
    ai_model: str = "claude-haiku-5-5"

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def validate(self) -> None:
        if self.ai_mode not in {"disabled", "demo", "external"}:
            raise ConfigError("AI_MODE must be disabled|demo|external")
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
        if not (self.google_client_id and self.google_client_secret):
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
        admin_emails=_list("ADMIN_EMAILS"),
        professor_emails=_list("PROFESSOR_EMAILS"),
        allowed_email_domains=_list("ALLOWED_EMAIL_DOMAINS"),
        dev_login_enabled=_bool("DEV_LOGIN_ENABLED", env in {"development", "test"}),
        session_ttl_hours=int(os.getenv("SESSION_TTL_HOURS", "12")),
        cookie_secure=_bool("COOKIE_SECURE", prod),
        # 익명 기능은 운영에서 보안 검토 후 명시적으로 켜야 한다
        feature_surveys=_bool("FEATURE_SURVEYS", not prod),
        feature_suggestions=_bool("FEATURE_SUGGESTIONS", not prod),
        ai_mode=os.getenv("AI_MODE", "disabled" if prod else "demo"),
        ai_api_key=os.getenv("AI_API_KEY", ""),
        ai_model=os.getenv("AI_MODEL", Settings.ai_model),
    )
    s.validate()
    return s
