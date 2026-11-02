"""의견 분석 (보조 기능).

모드
- disabled: 사용 불가
- demo: 외부 전송 없는 로컬 키워드 분석 (AI 아님을 명시)
- external: 외부 AI. 실패하면 로컬 분석으로 대체 → 기본 기능에 영향 없음
"""
from __future__ import annotations

import re
from collections import Counter

from sqlalchemy.orm import Session

from app.core.errors import Conflict, FeatureDisabled
from app.infra.ai_client import AIClient, ExternalAIError, prepare
from app.repositories import suggestions as sugg_repo
from app.services import survey_service

_TOKEN = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_JOSA = ("으로", "에서", "에게", "하고", "이랑", "까지", "부터", "은", "는", "이", "가", "을", "를", "에", "의",
         "도", "로", "와", "과", "만", "요")
STOP = {"그리고", "그냥", "너무", "정말", "조금", "좀", "수업", "교수님", "있어요", "있습니다", "합니다", "해요",
        "같아요", "것", "같습니다", "있으면", "하면", "때문에", "있는", "없는", "the", "and"}
POSITIVE = ("좋", "감사", "만족", "도움", "재미", "유익", "최고", "친절", "명확")
IMPROVE = ("어렵", "불편", "개선", "부족", "느리", "빠르", "힘들", "많아", "많습", "늦", "안 ", "않", "없", "아쉽",
           "헷갈", "바꿔", "줄여", "늘려")


def _norm(tok: str) -> str:
    for j in _JOSA:
        if tok.endswith(j) and len(tok) - len(j) >= 2:
            return tok[: -len(j)]
    return tok


def classify(text: str) -> str:
    imp = any(k in text for k in IMPROVE)
    pos = any(k in text for k in POSITIVE)
    if imp:
        return "improvement"
    if pos:
        return "positive"
    return "other"


def local_analyze(items: list[str], top: int = 8) -> dict:
    df: Counter[str] = Counter()
    where: dict[str, list[int]] = {}
    for i, t in enumerate(items):
        toks = {_norm(x.lower()) for x in _TOKEN.findall(t)}
        for tok in toks - STOP:
            df[tok] += 1
            where.setdefault(tok, []).append(i)
    kinds = Counter(classify(t) for t in items)
    themes = [{"title": k, "kind": "keyword", "count": n,
               "examples": [items[i][:120] for i in where[k][:2]]}
              for k, n in df.most_common(top) if n >= 2]
    return {
        "engine": "local-keyword",
        "notice": "외부 전송 없이 서버에서 키워드 빈도로 계산한 결과입니다 (AI 아님).",
        "total": len(items),
        "classification": {"positive": kinds["positive"], "improvement": kinds["improvement"],
                           "other": kinds["other"]},
        "summary": (f"총 {len(items)}건 중 개선 의견으로 보이는 것 {kinds['improvement']}건, "
                    f"긍정 의견 {kinds['positive']}건, 기타 {kinds['other']}건입니다."),
        "themes": themes,
        "actions": [],
    }


def _validate_external(raw: dict, items: list[str]) -> dict:
    themes = []
    for th in raw.get("themes", [])[:10]:
        ids = [i for i in th.get("item_ids", []) if isinstance(i, int) and 0 <= i < len(items)]
        if not ids:  # 근거 없는 주제는 버린다
            continue
        kind = th.get("kind") if th.get("kind") in ("positive", "improvement", "other") else "other"
        themes.append({"title": str(th.get("title", ""))[:100], "kind": kind, "count": len(ids),
                       "examples": [items[i][:120] for i in ids[:2]]})
    return {
        "engine": "external-ai",
        "notice": "외부 AI가 생성한 요약입니다. 근거 예시는 원문에서 가져왔지만 요약 문장은 반드시 직접 확인하세요.",
        "total": len(items),
        "summary": str(raw.get("summary", ""))[:1000],
        "themes": themes,
        "actions": [str(a)[:300] for a in raw.get("actions", [])[:5]],
    }


def collect_texts(db: Session, source: str, survey_id: int | None) -> list[str]:
    if source == "suggestions":
        return [s.content for s in sugg_repo.all_contents(db) if s.status != "archived"]
    if source == "survey" and survey_id is not None:
        res = survey_service.results(db, survey_id)
        if res["hidden"]:
            raise Conflict("최소 응답 수에 도달하지 않아 분석할 수 없습니다", code="below_threshold")
        return [t for q in res["questions"] for t in q.get("texts", [])]
    raise Conflict("분석 대상이 올바르지 않습니다")


def analyze(db: Session, mode: str, client: AIClient | None, source: str, survey_id: int | None) -> dict:
    if mode == "disabled":
        raise FeatureDisabled("의견 분석 기능이 비활성화되어 있습니다")
    texts = collect_texts(db, source, survey_id)
    if not texts:
        return {"engine": "none", "total": 0, "summary": "분석할 의견이 없습니다.", "themes": [], "actions": []}
    if mode == "external" and client is not None:
        items = prepare(texts)
        try:
            return _validate_external(client.analyze(items), items)
        except ExternalAIError:
            result = local_analyze(texts)
            result["notice"] = "외부 AI 호출에 실패해 로컬 키워드 분석으로 대체했습니다."
            return result
    return local_analyze(texts)

