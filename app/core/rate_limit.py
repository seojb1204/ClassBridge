"""메모리 기반 슬라이딩 윈도 요청 제한.

익명 기능에 쓸 때의 원칙: 키별 '시각 목록'만 잠시 보관하고, 제출 내용과 연결하지 않으며,
디스크·로그에 남기지 않는다. 프로세스 재시작 시 사라진다 (단일 인스턴스 전제, docs 참고).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.errors import TooManyRequests


class RateLimiter:
    def __init__(self, rules: list[tuple[int, float]], clock=time.monotonic):
        # rules: [(허용 횟수, 초)]
        self.rules = rules
        self.clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._max_window = max(w for _, w in rules)

    def hit(self, key: str) -> None:
        now = self.clock()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self._max_window:
                q.popleft()
            for limit, window in self.rules:
                recent = sum(1 for t in q if now - t <= window)
                if recent >= limit:
                    raise TooManyRequests("요청이 너무 많습니다. 잠시 후 다시 시도해 주세요")
            q.append(now)
            if len(self._hits) > 10000:  # 메모리 보호
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
