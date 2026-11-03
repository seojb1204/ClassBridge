"""검증된 신원 정보 (인증 인프라 ↔ 사용자 서비스 사이의 공용 타입)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VerifiedIdentity:
    """Google ID 토큰 검증을 통과한 신원 정보. 요청 본문 값은 절대 여기에 들어오지 않는다."""

    sub: str
    email: str
    email_verified: bool
    name: str = ""
