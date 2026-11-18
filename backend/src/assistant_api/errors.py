"""Lỗi của assistant_api -> JSON {"detail": "<tiếng Việt>", "code": "<MA_LOI>"}."""

from http import HTTPStatus


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = int(status)


def unauthorized(code: str, message: str) -> ApiError:
    return ApiError(code, message, HTTPStatus.UNAUTHORIZED)


def forbidden(code: str, message: str) -> ApiError:
    return ApiError(code, message, HTTPStatus.FORBIDDEN)


def not_found(code: str, message: str) -> ApiError:
    return ApiError(code, message, HTTPStatus.NOT_FOUND)


def conflict(code: str, message: str) -> ApiError:
    return ApiError(code, message, HTTPStatus.CONFLICT)
