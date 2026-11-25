"""TN6 — vòng khép kín kho hỏi đáp (evaluation/run_knowledge.py): bộ ca, cách chấm, chạy giả lập."""

import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.common import load_config, read_jsonl  # noqa: E402
from evaluation.run_knowledge import (  # noqa: E402
    cites_knowledge,
    fully_supported,
    is_not_found,
    run_experiment,
    score,
    summarize,
)

from src.assistant_api.knowledge import personal_info_problem  # noqa: E402
from src.shared.db import get_assistant_engine  # noqa: E402

CASES = read_jsonl(ROOT / "evaluation" / "datasets" / "knowledge_cases.jsonl")


def test_dataset_is_well_formed() -> None:
    kho = [c for c in CASES if c["nhom"] == "kho"]
    assert len(kho) >= 10 and len([c for c in CASES if c["nhom"] == "ngoai_kho"]) >= 4
    assert len({c["id"] for c in CASES}) == len(CASES)
    for c in kho:
        # đáp án chỉ có trong câu trả lời của cán bộ, sinh viên hỏi khác câu trong kho
        assert any(a in c["tra_loi_kho"] for a in c["dap_an"]), c["id"]
        assert c["hoi_lai"] != c["cau_hoi_kho"]
        assert 10 <= len(c["cau_hoi_kho"]) <= 1000 and c["phong_ban"] in {
            "dao_tao", "ctsv", "tai_chinh", "khac",
        }  # fmt: skip
        # API kho sẽ chặn thông tin cá nhân -> bộ ca không được chứa
        assert personal_info_problem(c["cau_hoi_kho"] + " " + c["tra_loi_kho"]) is None


def test_not_found_detection() -> None:
    assert is_not_found("Văn bản hiện có không đề cập đến giờ mở cửa phòng gym.")
    assert is_not_found("Hệ thống không có dữ liệu về giờ mở cửa của phòng tập.")
    assert not is_not_found("Ký túc xá đóng cổng lúc 23 giờ [1].")


def test_citation_and_support_helpers() -> None:
    assert cites_knowledge([{"loai": "quy_che"}, {"loai": "hoi_dap"}])
    assert not cites_knowledge([{"loai": "quy_che"}, {}])
    assert fully_supported({"tong": 2, "co_can_cu": 2})
    assert not fully_supported({"tong": 2, "co_can_cu": 1})
    assert not fully_supported({"tong": 0, "co_can_cu": 0}) and not fully_supported(None)


def _result(answer: str, citations: list[dict[str, Any]], kc: dict | None) -> dict[str, Any]:
    return {"answer": answer, "citations": citations, "kiem_chung": kc, "tin_nhan_id": 7}


def test_score_knowledge_case_before_and_after() -> None:
    case = next(c for c in CASES if c["id"] == "K01")
    before = score(case, "truoc", _result("Văn bản không đề cập.", [], {"tong": 0}), {7})
    assert before["dung"] is False and before["khong_tim_thay"] and before["phat_hien_lo_hong"]
    after = score(
        case,
        "sau",
        _result(
            "Cổng KTX đóng lúc 23 giờ [1].", [{"loai": "hoi_dap"}], {"tong": 1, "co_can_cu": 1}
        ),  # noqa: E501
        set(),
    )
    assert after["dung"] and after["trich_kho"] and after["du_can_cu"]
    assert after["phat_hien_lo_hong"] is None  # chỉ đo ở pha trước


def test_score_control_case_uses_expected_answer() -> None:
    control = {"id": "A019", "nhom": "doi_chung", "hoi_lai": "Học phí?", "dap_an": ["350.000"]}
    row = score(control, "sau", _result("Học phí 350.000 đồng/tín chỉ [1].", [], None), set())
    assert row["dung"] and not row["trich_kho"]


def test_summarize_groups_by_group_and_phase() -> None:
    rows = [
        {"nhom": "kho", "pha": "truoc", "dung": False, "khong_tim_thay": True,
         "phat_hien_lo_hong": True, "trich_kho": False, "du_can_cu": False, "loi": ""},
        {"nhom": "kho", "pha": "sau", "dung": True, "khong_tim_thay": False,
         "phat_hien_lo_hong": None, "trich_kho": True, "du_can_cu": True, "loi": ""},
        {"nhom": "kho", "pha": "sau", "dung": False, "khong_tim_thay": True,
         "phat_hien_lo_hong": None, "trich_kho": False, "du_can_cu": False, "loi": ""},
    ]  # fmt: skip
    table = {(r["nhom"], r["pha"]): r for r in summarize(rows)}
    assert table[("kho", "sau")]["so_ca"] == 2 and table[("kho", "sau")]["dung"] == 0.5
    assert table[("kho", "truoc")]["phat_hien_lo_hong"] == 1.0
    assert table[("kho", "sau")]["phat_hien_lo_hong"] is None


def _counts() -> dict[str, int]:
    with get_assistant_engine().connect() as a:
        return {
            t: a.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()  # noqa: S608
            for t in ("kho_hoi_dap", "van_ban", "tin_nhan", "luot_goi_cong_cu")
        }


def test_dry_run_full_loop_leaves_no_data() -> None:
    before = _counts()
    rows, extra = run_experiment(load_config("knowledge"), dry_run=True, limit=2, controls=1)
    assert _counts() == before  # rollback: không để lại mục kho, văn bản, hội thoại
    phases = {(r["nhom"], r["pha"]) for r in rows}
    assert {("kho", "truoc"), ("kho", "sau"), ("doi_chung", "sau")} <= phases
    kho_after = [r for r in rows if r["nhom"] == "kho" and r["pha"] == "sau"]
    assert all(r["dung"] for r in kho_after)  # LLM giả trả đáp án ở pha sau
    assert all(r["phat_hien_lo_hong"] for r in rows if r["nhom"] == "kho" and r["pha"] == "truoc")
    assert extra["kho"]["trang_thai"] == "da_lap_chi_muc" and extra["kho"]["so_muc"] == 2
    assert extra["chan_thong_tin_ca_nhan"] == {"so_ca": 3, "bi_chan": 3}


def test_dry_run_selected_ids_still_fills_whole_knowledge_base() -> None:
    """--ids (chạy lại ca lỗi hạ tầng): chỉ hỏi các ca đã chọn, kho vẫn nạp đủ như lượt chính."""
    rows, extra = run_experiment(
        load_config("knowledge"), dry_run=True, limit=2, controls=1, ids=["K01"]
    )
    assert {(r["id"], r["pha"]) for r in rows} == {("K01", "truoc"), ("K01", "sau")}
    assert extra["kho"]["so_muc"] == 2
