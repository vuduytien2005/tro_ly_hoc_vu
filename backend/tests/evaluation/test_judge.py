"""TN2: faithfulness theo mệnh đề (LLM-làm-giám-khảo) + đối chiếu chấm tay — hàm thuần, LLM giả."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation import doi_chieu_cham_tay, metrics, run_rag_answer  # noqa: E402

FOUND = [{"so": 1, "noi_dung": "Điều 10. ..."}, {"so": 2, "noi_dung": "Điều 12. ..."}]


def claim(text: str, verdict: str, refs: list[Any]) -> dict[str, Any]:
    return {"noi_dung": text, "ket_luan": verdict, "can_cu": refs}


def test_parse_claims_normalizes_and_is_cautious() -> None:
    claims = metrics.parse_claims(
        {
            "menh_de": [
                claim("Tối đa 2 học kỳ", "co_can_cu", [1, "2", "x"]),
                claim("  ", "co_can_cu", [1]),  # rỗng -> bỏ
                claim("Nộp ở phòng CTSV", "chac_chan_dung", [2]),  # kết luận lạ -> khong_can_cu
                "không phải object",
            ]
        }
    )
    assert [c["noi_dung"] for c in claims] == ["Tối đa 2 học kỳ", "Nộp ở phòng CTSV"]
    assert claims[0]["can_cu"] == [1, 2]
    assert claims[1]["ket_luan"] == "khong_can_cu"
    assert metrics.parse_claims(None) == [] and metrics.parse_claims({"menh_de": "x"}) == []


def test_claim_faithfulness_requires_real_passage() -> None:
    claims = metrics.parse_claims(
        {
            "menh_de": [
                claim("A", "co_can_cu", [1]),
                claim("B", "co_can_cu", [7]),  # viện dẫn đoạn không có trong ngữ cảnh
                claim("C", "co_can_cu", []),  # không chỉ ra căn cứ
                claim("D", "mau_thuan", [2]),
            ]
        }
    )
    out = metrics.claim_faithfulness(claims, [d["so"] for d in FOUND])
    assert out["so_menh_de"] == 4 and out["co_can_cu"] == 1 and out["mau_thuan"] == 1
    assert out["ty_le"] == pytest.approx(0.25)
    assert out["khong_can_cu"] == ["B", "C", "D"]


def test_claim_faithfulness_no_claims_is_none() -> None:
    assert metrics.claim_faithfulness([], [1])["ty_le"] is None


def fake_completion(content: str) -> Any:
    def call(**_: Any) -> Any:
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )

    return call


def test_judge_claims_parses_model_output(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps(
        {"menh_de": [claim("A", "co_can_cu", [1]), claim("B", "khong_can_cu", [])]},
        ensure_ascii=False,
    )
    monkeypatch.setattr(
        run_rag_answer, "_completion_with_wait", fake_completion(f"Kết quả:\n```json\n{body}\n```")
    )
    out = run_rag_answer.judge_claims("m", "[1] ...", "Trả lời", FOUND)
    assert out["ty_le"] == 0.5 and out["khong_can_cu"] == ["B"]
    assert out["token_vao"] == 100 and out["token_ra"] == 20


def test_judge_claims_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_rag_answer, "_completion_with_wait", fake_completion("xin lỗi {sai"))
    out = run_rag_answer.judge_claims("m", "", "Trả lời", FOUND)
    assert out["ty_le"] is None and out["loi"].startswith("Không đọc được JSON")


def test_spearman_and_agreement() -> None:
    assert metrics.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert metrics.spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert metrics.spearman([1, 1, 1], [1, 2, 3]) is None
    assert metrics.spearman([1, 2], [1, 2]) is None
    assert [metrics.to_manual_scale(x) for x in (0.0, 0.3, 0.5, 0.7, 1.0)] == [0, 0, 1, 2, 2]
    out = metrics.manual_agreement([(2, 1.0), (1, 0.5), (0, 0.75)])
    assert out["n"] == 3 and out["trung_khop"] == pytest.approx(2 / 3)
    assert out["sai_lech_tb"] == pytest.approx(0.25)
    assert metrics.manual_agreement([])["trung_khop"] is None


def test_compare_manual_grades() -> None:
    rows = [
        {"cham_tay": "2", "cham_tay_2": "2", "relevancy": "1.0", "faithfulness_menh_de": "1.0"},
        {"cham_tay": "1", "cham_tay_2": "2", "relevancy": "0.5", "faithfulness_menh_de": ""},
        {"cham_tay": "0", "cham_tay_2": "0", "relevancy": "0.0", "faithfulness_menh_de": "0.2"},
        {"cham_tay": "", "cham_tay_2": "", "relevancy": "1.0", "faithfulness_menh_de": "1.0"},
    ]
    table, between = doi_chieu_cham_tay.compare(rows)
    first = next(
        t
        for t in table
        if t["nguoi_cham"] == "Người chấm 1" and t["diem_tu_dong"].startswith("Rel")
    )
    assert first["n"] == 3 and first["trung_khop"] == 1.0
    assert between is not None and between["n"] == 3
    assert between["trung_khop"] == pytest.approx(2 / 3)
    assert "Đồng thuận" in doi_chieu_cham_tay.render(table, between)
    with pytest.raises(ValueError):
        doi_chieu_cham_tay.compare([{"cham_tay": "5"}])
