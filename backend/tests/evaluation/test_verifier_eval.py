"""TN5 — kiểm chứng câu trả lời: cách chấm (evaluation/run_verifier.py) + bộ ca hợp lệ."""

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.common import read_jsonl  # noqa: E402
from evaluation.run_verifier import flagged, summarize  # noqa: E402

CASES = read_jsonl(ROOT / "evaluation" / "datasets" / "verifier_cases.jsonl")


def result(*claims: tuple[str, str]) -> dict[str, Any]:
    return {
        "tong": len(claims),
        "co_can_cu": sum(k == "co_can_cu" for _, k in claims),
        "y": [{"cau": c, "ket_luan": k, "doan": [], "ly_do": ""} for c, k in claims],
    }


def test_dataset_is_well_formed() -> None:
    assert 25 <= len(CASES) <= 35
    assert len({c["id"] for c in CASES}) == len(CASES)
    for c in CASES:
        assert c["y_sai"] in c["tra_loi_sai"] and c["y_sai"] not in c["tra_loi_dung"]
        assert c["tra_loi_dung"] != c["tra_loi_sai"]
        assert set(c["doan"]) >= {"1"}
        assert c["loai_loi"] in {"so_lieu", "thoi_han", "dieu_kien", "phien_ban"}


def test_flagged_matches_planted_sentence() -> None:
    bad = "Mỗi học phần có từ 2 đến 6 tín chỉ [1]."
    assert flagged(result(("Mỗi học phần có từ 2 đến 6 tín chỉ [1].", "khong_co_can_cu")), bad)
    # giám khảo trích một phần câu (không có [n]) vẫn tính là bắt được
    assert flagged(result(("có từ 2 đến 6 tín chỉ", "khong_co_can_cu")), bad)
    assert not flagged(result(("Mỗi học phần có từ 2 đến 6 tín chỉ [1].", "co_can_cu")), bad)
    assert not flagged(None, bad)


def test_summarize_recall_and_false_alarm() -> None:
    rows = [
        {"loai_loi": "so_lieu", "bat_duoc": True, "bao_nham": False, "thoi_gian_ms": 100,
         "token_vao": 10, "token_ra": 5, "loi": ""},
        {"loai_loi": "so_lieu", "bat_duoc": False, "bao_nham": True, "thoi_gian_ms": 300,
         "token_vao": 10, "token_ra": 5, "loi": ""},
    ]  # fmt: skip
    total, by_kind = summarize(rows)
    assert total["recall"] == 0.5 and total["bao_nham"] == 0.5
    assert total["thoi_gian_tb_ms"] == 200 and total["so_ca"] == 2
    assert by_kind[0]["loai_loi"] == "so_lieu" and by_kind[0]["recall"] == 0.5
