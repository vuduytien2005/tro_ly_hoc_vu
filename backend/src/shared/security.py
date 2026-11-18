"""Xác thực nội bộ giữa các service (qlsv_api, MCP servers, assistant_api)."""

import hmac

from src.shared.config import get_settings

INTERNAL_TOKEN_HEADER = "X-Internal-Token"


def is_valid_internal_token(token: str | None) -> bool:
    """So sánh thời gian hằng (hmac.compare_digest) để không lộ token qua thời gian phản hồi."""
    if not token:
        return False
    expected = get_settings().internal_api_token
    return hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8"))
