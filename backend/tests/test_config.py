"""Quy tắc bảo mật 4: không khởi động với bí mật yếu / chuỗi mẫu của .env.example."""

import pytest
from pydantic import ValidationError

from src.shared.config import Settings

STRONG = "Kx9-Qm2_vT7pLr4Zs8Wn3Yb6Hc1Jd5Fg0"


def make(**overrides: str) -> Settings:
    values = {"jwt_secret": STRONG, "internal_api_token": STRONG, **overrides}
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "ngan_qua",
        "thay_bang_chuoi_ngau_nhien",
        "THAY_BANG_chuoi_ngau_nhien_khac" * 3,
        "A" * 64,
    ],
)
@pytest.mark.parametrize("field", ["jwt_secret", "internal_api_token"])
def test_weak_or_placeholder_secret_is_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError) as exc:
        make(**{field: value})
    assert field.upper() in str(exc.value)
    assert "secrets.token_urlsafe" in str(exc.value)  # hướng dẫn cách tạo chuỗi


def test_strong_secret_is_accepted_and_trimmed() -> None:
    settings = make(jwt_secret=f"  {STRONG}  ")
    assert settings.jwt_secret == STRONG
