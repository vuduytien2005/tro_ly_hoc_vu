"""Script PowerShell phải là UTF-8 CÓ BOM: Windows PowerShell 5.1 (mặc định trên Windows) đọc
file không BOM theo bảng mã ANSI -> tiếng Việt vỡ, có thể hỏng cả cú pháp."""

from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).resolve().parents[1] / "scripts").glob("*.ps1"))


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_powershell_script_has_utf8_bom(script: Path) -> None:
    assert script.read_bytes().startswith(b"\xef\xbb\xbf")
