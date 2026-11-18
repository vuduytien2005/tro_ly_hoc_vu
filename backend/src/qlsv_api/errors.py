"""Lỗi nghiệp vụ của hệ thống QLSV giả lập.

Tầng services/ chỉ ném `BusinessError`, KHÔNG phụ thuộc FastAPI. main.py chuyển lỗi
này thành JSON `{"detail": "<tiếng Việt>", "code": "<MA_LOI>"}` với mã HTTP tương ứng.
"""

from http import HTTPStatus


class BusinessError(Exception):
    def __init__(self, code: str, message: str, status: int = HTTPStatus.CONFLICT) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = int(status)


def not_found(code: str, message: str) -> BusinessError:
    return BusinessError(code, message, HTTPStatus.NOT_FOUND)


def conflict(code: str, message: str) -> BusinessError:
    return BusinessError(code, message, HTTPStatus.CONFLICT)


def invalid(code: str, message: str) -> BusinessError:
    return BusinessError(code, message, HTTPStatus.UNPROCESSABLE_ENTITY)
