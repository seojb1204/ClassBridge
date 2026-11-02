"""외부 AI 연동 (기본 비활성).

- 입력은 건의·설문 자유응답 텍스트뿐이다. 상담 기록은 이 모듈로 전달될 경로 자체가 없다.
- 전송 전 이메일·전화번호·학번으로 보이는 숫자를 마스킹한다.
- 응답의 '인용'은 AI가 쓴 문장이 아니라 원문 항목 번호로만 받아 서버가 원문을 붙인다 → 지어낸 인용 차단.
"""
from __future__ import annotations

import json
import re
from typing import Protocol

import httpx

from app.config import Settings

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}")
_LONGNUM = re.compile(r"\d{7,}")
MAX_ITEMS = 200
MAX_CHARS = 30000


def scrub(text: str) -> str:
    text = _EMAIL.sub("[이메일]", text)
    text = _PHONE.sub("[전화번호]", text)
    return _LONGNUM.sub("[번호]", text)


def prepare(texts: list[str]) -> list[str]:
    out, total = [], 0
    for t in texts[:MAX_ITEMS]:
        t = scrub(t)[:1000]
        if total + len(t) > MAX_CHARS:
            break
        out.append(t)
        total += len(t)
    return out


class AIClient(Protocol):
    name: str

    def analyze(self, items: list[str]) -> dict: ...


class ExternalAIError(RuntimeError):
    pass


PROMPT = """다음은 수업에 대한 학생들의 익명 의견 목록이다. 각 줄은 [번호] 의견 형식이다.
목록에 실제로 있는 내용만 근거로 분석하라. 목록에 없는 사실을 만들지 마라.
반드시 아래 JSON 하나만 출력하라:
{"summary": "3문장 이내 요약",
 "themes": [{"title": "반복되는 주제", "kind": "positive|improvement|other", "item_ids": [근거 번호들]}],
 "actions": ["수업 개선 제안 (근거가 있는 것만)"]}

의견 목록:
"""


class AnthropicClient:
    name = "external"

    def __init__(self, api_key: str, model: str, timeout: float = 30.0):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def analyze(self, items: list[str]) -> dict:
        body = PROMPT + "\n".join(f"[{i}] {t}" for i, t in enumerate(items))
        try:
            r = httpx.post("https://api.anthropic.com/v1/messages", timeout=self.timeout, headers={
                "x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json",
            }, json={"model": self.model, "max_tokens": 1500, "messages": [{"role": "user", "content": body}]})
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json().get("content", []))
            start, end = text.find("{"), text.rfind("}")
            return json.loads(text[start:end + 1])
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ExternalAIError(type(exc).__name__) from exc


def build_ai_client(settings: Settings) -> AIClient | None:
    if settings.ai_mode == "external" and settings.ai_api_key:
        return AnthropicClient(settings.ai_api_key, settings.ai_model)
    return None
