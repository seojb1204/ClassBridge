"""서비스 계층 예외. HTTP와 무관하게 정의하고 main.py에서 상태 코드로 변환한다."""
from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class BadRequest(AppError):
    status_code = 400
    code = "bad_request"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class FeatureDisabled(AppError):
    status_code = 503
    code = "feature_disabled"


class TooManyRequests(AppError):
    status_code = 429
    code = "too_many_requests"
