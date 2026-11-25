"""TN6 — chẩn đoán phần TRUY XUẤT (không gọi LLM, miễn phí): với từng câu hỏi của TN6, đoạn kho
đúng đứng hạng mấy trong kết quả search_regulations (top-5, như trợ lý), và đoạn kho có chen vào
kết quả của câu hỏi quy chế (đối chứng) không.

    python evaluation\\chan_doan_kho.py

Dùng cùng môi trường harness (CSDL rollback, Chroma tạm, embedding thật), nạp kho qua API thật.
Câu hỏi đưa vào tìm kiếm = nguyên văn câu sinh viên (trợ lý thật có thể viết lại câu truy vấn).
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.common import bootstrap, load_config, markdown_table, new_run_dir, write_csv  # noqa: E402

bootstrap()

from evaluation.run_knowledge import STUDENT, clear_knowledge, load_cases  # noqa: E402

TOP_K = 5


def ranks(retriever: Any, question: str, ma_khoa: str) -> list[dict[str, Any]]:
    return [
        {"loai": c.loai, "dieu": c.dieu, "van_ban": c.van_ban}
        for c in retriever.search(question, ma_khoa, TOP_K)
    ]


def main() -> int:
    from src.rag import retriever as rag

    from evaluation.harness import AgentHarness, ma_khoa_of

    config = load_config("knowledge")
    cases = load_cases(config, None, None)
    rows = []
    with AgentHarness(config, dry_run=False) as harness:
        clear_knowledge(harness)
        retriever = rag.get_retriever()
        before = {
            c["id"]: ranks(retriever, c["hoi_lai"], ma_khoa_of(c.get("dang_nhap") or STUDENT))
            for c in cases
        }
        for c in [c for c in cases if c["nhom"] == "kho"]:
            r = harness.client.post(
                "/api/admin/knowledge",
                json={
                    "cau_hoi": c["cau_hoi_kho"],
                    "tra_loi": c["tra_loi_kho"],
                    "phong_ban": c["phong_ban"],
                },
                headers=harness.admin_headers(),
            )
            assert r.status_code == 201, r.text
        for c in cases:
            hits = ranks(retriever, c["hoi_lai"], ma_khoa_of(c.get("dang_nhap") or STUDENT))
            own = (
                next(
                    (
                        i
                        for i, h in enumerate(hits, start=1)
                        if h["loai"] == "hoi_dap" and c["cau_hoi_kho"] in (h["dieu"] or "")
                    ),
                    None,
                )
                if c["nhom"] == "kho"
                else None
            )
            reg_before = [h["dieu"] for h in before[c["id"]] if h["loai"] != "hoi_dap"]
            reg_after = [h["dieu"] for h in hits if h["loai"] != "hoi_dap"]
            rows.append(
                {
                    "id": c["id"],
                    "nhom": c["nhom"],
                    "hang_doan_kho_dung": own,
                    "so_doan_kho_trong_top": sum(h["loai"] == "hoi_dap" for h in hits),
                    "dieu_quy_che_bi_day_ra": len(set(reg_before) - set(reg_after)),
                    "top": [f"{h['loai']}:{h['dieu']}" for h in hits],
                }
            )
    run_dir = new_run_dir("tn6_chan_doan_truy_xuat")
    write_csv(run_dir / "chi_tiet.csv", rows)
    table = markdown_table(
        rows,
        [
            ("id", "Ca"),
            ("nhom", "Nhóm"),
            ("hang_doan_kho_dung", "Hạng đoạn kho đúng"),
            ("so_doan_kho_trong_top", f"Số đoạn kho trong top-{TOP_K}"),
            ("dieu_quy_che_bi_day_ra", "Điều quy chế bị đẩy ra"),
        ],
    )
    (run_dir / "tong_hop.md").write_text(table + "\n", encoding="utf-8")
    print(table)
    print(f"\nKết quả: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
