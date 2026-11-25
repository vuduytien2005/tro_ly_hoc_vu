"""TN6 — Vòng khép kín kho hỏi đáp: lỗ hổng tri thức -> cán bộ trả lời -> trợ lý trả lời được.

    python evaluation\\run_knowledge.py --dry-run          # LLM giả, 2 ca/nhóm, miễn phí
    python evaluation\\run_knowledge.py                    # cấu hình knowledge (Gemini)
    python evaluation\\run_knowledge.py --limit 5 --controls 4

Trợ lý THẬT (harness: assistant_api + MCP + qlsv trong tiến trình, CSDL rollback), có giám khảo
kiểm chứng như lúc chạy demo. Ba pha trên CÙNG một môi trường:
1. Trước: sinh viên hỏi (cách diễn đạt của sinh viên, khác câu trong kho). Đo: trợ lý trả lời
   "không tìm thấy" thay vì bịa; trang Lỗ hổng tri thức (GET /api/admin/knowledge/gaps) có
   phát hiện tin nhắn đó (nguồn khong_tim_thay / khong_can_cu) không.
2. Nạp: quản trị viên viết câu trả lời vào kho qua API thật (POST /api/admin/knowledge, liên kết
   tin nhắn ở pha 1) -> quy_che lập chỉ mục lại. Kèm 3 bản nháp có thông tin cá nhân: phải bị chặn.
3. Sau: hỏi lại y hệt (hội thoại mới). Đo: trả lời đúng (chứa chi tiết chỉ có trong câu trả lời
   của cán bộ), trích dẫn kho, giám khảo xác nhận đủ căn cứ.
Nhóm đối chứng (câu quy chế, agent_scenarios.jsonl loai chi_rag): kho không được làm giảm độ
chính xác. Nhóm ngoài kho: không có ở đâu -> vẫn phải trả lời "không tìm thấy" (không bám nhầm kho).
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.common import (  # noqa: E402
    ROOT,
    bootstrap,
    dataset_path,
    load_config,
    markdown_table,
    mean,
    new_run_dir,
    progress,
    read_jsonl,
    save_configs,
    write_csv,
)

bootstrap()

from evaluation import metrics  # noqa: E402

STUDENT = "SV22001"
PHASES = ("truoc", "sau")
GROUPS = ("kho", "ngoai_kho", "doi_chung")
# Ngoài REFUSAL_PHRASES của TN2/TN3 (giữ nguyên để không đổi số liệu cũ): cách nói "không có" hay
# gặp khi thử thật (vd "hệ thống không có dữ liệu về giờ mở cửa")
EXTRA_NOT_FOUND = ("không có dữ liệu", "chưa có dữ liệu", "không nêu", "chưa có quy định")
RATE_KEYS = ("dung", "khong_tim_thay", "phat_hien_lo_hong", "trich_kho", "du_can_cu")
# Bản nháp có thông tin cá nhân: API phải từ chối 422 (kho trả cho mọi sinh viên)
PERSONAL_DRAFTS = (
    ("Em SV22001 hỏi ký túc xá mấy giờ đóng cửa?", "Ký túc xá đóng cổng lúc 23 giờ."),
    ("Ký túc xá đóng cửa lúc mấy giờ?", "Liên hệ chị Lan qua lan.nguyen@truong.example."),
    ("Ký túc xá đóng cửa lúc mấy giờ?", "Gọi số 0912 345 678 để hỏi ban quản lý."),
)


# ----- chấm ---------------------------------------------------------------------------
def is_not_found(answer: str) -> bool:
    text = metrics.norm(answer)
    return metrics.is_refusal(answer) or any(metrics.norm(p) in text for p in EXTRA_NOT_FOUND)


def cites_knowledge(citations: list[dict[str, Any]] | None) -> bool:
    return any(c.get("loai") == "hoi_dap" for c in citations or [])


def fully_supported(verification: dict[str, Any] | None) -> bool:
    """Giám khảo tìm được ít nhất một ý và mọi ý đều có căn cứ."""
    return (
        bool(verification)
        and verification.get("tong", 0) > 0
        and (  # type: ignore[union-attr]
            verification["co_can_cu"] == verification["tong"]  # type: ignore[index]
        )
    )


def score(
    case: dict[str, Any], phase: str, result: dict[str, Any], gap_ids: set[int]
) -> dict[str, Any]:
    answer = result.get("answer") or ""
    verification = result.get("kiem_chung")
    expected = case.get("dap_an")
    return {
        "id": case["id"],
        "nhom": case["nhom"],
        "pha": phase,
        "hoi": case["hoi_lai"],
        "dung": metrics.answer_contains(answer, expected) if expected else None,
        "khong_tim_thay": is_not_found(answer),
        "phat_hien_lo_hong": (result.get("tin_nhan_id") in gap_ids) if phase == "truoc" else None,
        "trich_kho": cites_knowledge(result.get("citations")),
        "du_can_cu": fully_supported(verification),
        "so_y": verification.get("tong") if verification else None,
        "y_co_can_cu": verification.get("co_can_cu") if verification else None,
        "giay": result.get("giay"),
        "token_vao": result.get("token_vao"),
        "token_ra": result.get("token_ra"),
        "tra_loi": answer,
        "loi": result.get("loi") or "",
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Một dòng cho mỗi (nhóm, pha); tỉ lệ chỉ tính trên ca có giá trị (None = không áp dụng)."""
    out = []
    keys = sorted(
        {(r["nhom"], r["pha"]) for r in rows},
        key=lambda k: (GROUPS.index(k[0]) if k[0] in GROUPS else 9, PHASES.index(k[1])),
    )
    for group, phase in keys:
        items = [r for r in rows if r["nhom"] == group and r["pha"] == phase]
        line: dict[str, Any] = {"nhom": group, "pha": phase, "so_ca": len(items)}
        for key in RATE_KEYS:
            values = [r[key] for r in items if r.get(key) is not None]
            line[key] = mean(1.0 if v else 0.0 for v in values) if values else None
        line["giay_tb"] = mean(r.get("giay") for r in items)
        line["so_loi"] = sum(1 for r in items if r.get("loi"))
        out.append(line)
    return out


# ----- chạy ---------------------------------------------------------------------------
def load_cases(config: dict[str, Any], limit: int | None, controls: int | None) -> list[dict]:
    cases = read_jsonl(dataset_path(config, "knowledge_cases.jsonl"))
    kho = [c for c in cases if c["nhom"] == "kho"][:limit]
    outside = [c for c in cases if c["nhom"] == "ngoai_kho"][:limit]
    scenarios = read_jsonl(ROOT / "evaluation" / "datasets" / "agent_scenarios.jsonl")
    control = [
        {
            "id": s["id"],
            "nhom": "doi_chung",
            "hoi_lai": s["yeu_cau"],
            "dap_an": s["ket_qua_mong_doi"],
            "dang_nhap": s["dang_nhap"],
        }
        for s in scenarios
        if s["loai"] == "chi_rag"
    ][:controls]
    return kho + outside + control


def dry_text(case: dict[str, Any], phase: str) -> str:
    if case["nhom"] == "doi_chung" or (case["nhom"] == "kho" and phase == "sau"):
        return f"Theo văn bản, {case['dap_an'][0]} [1]."
    return "Văn bản hiện có không đề cập đến nội dung này."


def ask(harness: Any, case: dict[str, Any], phase: str) -> dict[str, Any]:
    question = case["hoi_lai"]
    steps = [("search_regulations", harness.fill_required("search_regulations", {}, question))]
    harness.use_llm(steps, dry_text(case, phase))
    if harness.verifier is not None:
        harness.verifier.reset()
    r = harness.run(case.get("dang_nhap") or STUDENT, question, auto_confirm=False)
    verifier = harness.verifier
    return {
        "answer": r.last_answer,
        "citations": r.citations,
        "kiem_chung": r.kiem_chung,
        "tin_nhan_id": r.tin_nhan_id,
        "giay": round(r.seconds, 2),
        "token_vao": r.tokens_in + (verifier.tokens_in if verifier else 0),
        "token_ra": r.tokens_out + (verifier.tokens_out if verifier else 0),
        "loi": r.error,
    }


def gap_message_ids(harness: Any) -> set[int]:
    ids: set[int] = set()
    for source in ("khong_tim_thay", "khong_can_cu"):
        r = harness.client.get(
            f"/api/admin/knowledge/gaps?ngay=365&nguon={source}", headers=harness.admin_headers()
        )
        r.raise_for_status()
        ids |= {m["tin_nhan_id"] for m in r.json()["muc"] if m.get("tin_nhan_id")}
    return ids


def clear_knowledge(harness: Any) -> None:
    """Bắt đầu từ kho rỗng (CSDL dev có thể có mục thật; mọi thay đổi bị rollback cuối lượt)."""
    from sqlalchemy import delete
    from src.assistant_api.models import KhoHoiDap, VanBan

    with harness.iso.factory() as db:
        db.execute(delete(KhoHoiDap))
        db.execute(delete(VanBan).where(VanBan.loai == "hoi_dap"))
        db.commit()


def fill_knowledge(
    harness: Any, kho: list[dict[str, Any]], before: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    admin = harness.admin_headers()
    seconds, failed = [], []
    for case in kho:
        started = time.perf_counter()
        r = harness.client.post(
            "/api/admin/knowledge",
            json={
                "cau_hoi": case["cau_hoi_kho"],
                "tra_loi": case["tra_loi_kho"],
                "phong_ban": case["phong_ban"],
                "tin_nhan_id": before.get(case["id"], {}).get("tin_nhan_id"),
            },
            headers=admin,
        )
        seconds.append(time.perf_counter() - started)  # gồm lập chỉ mục lại toàn bộ kho
        if r.status_code != 201:
            failed.append(f"{case['id']}: HTTP {r.status_code} {r.text[:120]}")
    blocked = 0
    for question, answer in PERSONAL_DRAFTS:
        r = harness.client.post(
            "/api/admin/knowledge",
            json={"cau_hoi": question, "tra_loi": answer, "phong_ban": "ctsv"},
            headers=admin,
        )
        blocked += r.status_code == 422 and r.json().get("code") == "CO_THONG_TIN_CA_NHAN"
    kb = harness.client.get("/api/admin/knowledge", headers=admin).json()
    doc = kb.get("van_ban") or {}
    gaps = harness.client.get("/api/admin/knowledge/gaps?ngay=365", headers=admin).json()
    linked = {before[c["id"]]["tin_nhan_id"] for c in kho if c["id"] in before}
    marked = [m for m in gaps["muc"] if m.get("tin_nhan_id") in linked]
    return {
        "kho": {
            "so_muc": len(kb["muc"]),
            "trang_thai": doc.get("trang_thai"),
            "so_doan": doc.get("so_doan"),
            "loi": failed or doc.get("loi"),
            "giay_luu_va_lap_chi_muc_tb": round(mean(seconds), 3) if seconds else None,
        },
        "chan_thong_tin_ca_nhan": {"so_ca": len(PERSONAL_DRAFTS), "bi_chan": blocked},
        "lo_hong_danh_dau_da_vao_kho": {
            "so_muc": len(marked),
            "da_vao_kho": sum(1 for m in marked if m["da_vao_kho"]),
        },
    }


def run_experiment(
    config: dict[str, Any],
    dry_run: bool,
    limit: int | None = None,
    controls: int | None = None,
    ids: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """`ids`: chỉ HỎI các ca này (chạy lại ca lỗi hạ tầng); kho vẫn nạp đủ như lượt chính."""
    from evaluation.harness import AgentHarness

    loaded = load_cases(config, limit, controls)
    kho = [c for c in loaded if c["nhom"] == "kho"]
    cases = [c for c in loaded if not ids or c["id"] in ids]
    rows: list[dict[str, Any]] = []
    total = len(cases) * 2
    with AgentHarness(config, dry_run) as harness:
        clear_knowledge(harness)
        before: dict[str, dict[str, Any]] = {}
        for i, case in enumerate(cases, start=1):
            before[case["id"]] = ask(harness, case, "truoc")
            progress(i, total, f"trước {case['id']}: {before[case['id']]['answer'][:60]!r}")
        gap_ids = gap_message_ids(harness)
        rows += [score(c, "truoc", before[c["id"]], gap_ids) for c in cases]

        extra = fill_knowledge(harness, kho, before)
        print(f"   nạp kho: {extra['kho']}")

        for i, case in enumerate(cases, start=len(cases) + 1):
            after = ask(harness, case, "sau")
            rows.append(score(case, "sau", after, set()))
            progress(i, total, f"sau {case['id']}: {after['answer'][:60]!r}")
        usage = {
            "token_vao": sum(r["token_vao"] or 0 for r in rows),
            "token_ra": sum(r["token_ra"] or 0 for r in rows),
        }
    counts = {g: sum(c["nhom"] == g for c in cases) for g in GROUPS}
    return rows, {**extra, **usage, "so_ca": counts}


GROUP_LABELS = {"kho": "Có trong kho", "ngoai_kho": "Ngoài kho", "doi_chung": "Đối chứng (quy chế)"}
PHASE_LABELS = {"truoc": "Trước khi nạp kho", "sau": "Sau khi nạp kho"}


def report(config: dict[str, Any], model: str, table: list[dict[str, Any]], extra: dict) -> str:
    shown = [
        {**t, "nhom": GROUP_LABELS.get(t["nhom"], t["nhom"]), "pha": PHASE_LABELS[t["pha"]]}
        for t in table
    ]
    columns = [
        ("nhom", "Nhóm"),
        ("pha", "Pha"),
        ("so_ca", "Số ca"),
        ("dung", "Trả lời đúng"),
        ("khong_tim_thay", "Nói không tìm thấy"),
        ("phat_hien_lo_hong", "Trang Lỗ hổng phát hiện"),
        ("trich_kho", "Trích dẫn kho"),
        ("du_can_cu", "Giám khảo: đủ căn cứ"),
        ("giay_tb", "Thời gian TB (s)"),
        ("so_loi", "Lỗi"),
    ]
    k, c, m = extra["kho"], extra["chan_thong_tin_ca_nhan"], extra["lo_hong_danh_dau_da_vao_kho"]
    return "\n\n".join(
        [
            f"# TN6 — Vòng khép kín kho hỏi đáp ({config['ma']}, {model})",
            markdown_table(shown, columns, percent=RATE_KEYS),
            "## Nạp kho",
            f"- Mục đã lưu: {k['so_muc']}, văn bản kho: {k['trang_thai']} ({k['so_doan']} đoạn), "
            f"lưu + lập chỉ mục lại TB {k['giay_luu_va_lap_chi_muc_tb']} s/mục; lỗi: {k['loi']}",
            f"- Bản nháp có thông tin cá nhân bị chặn: {c['bi_chan']}/{c['so_ca']}",
            f'- Trang Lỗ hổng đánh dấu "Đã có trong kho": {m["da_vao_kho"]}/{m["so_muc"]}',
            f"- Token (trợ lý + giám khảo): vào {extra['token_vao']}, ra {extra['token_ra']}",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="knowledge")
    parser.add_argument("--limit", type=int, help="số ca tối đa mỗi nhóm kho / ngoài kho")
    parser.add_argument("--controls", type=int, help="số câu đối chứng (mặc định: tất cả chi_rag)")
    parser.add_argument("--ids", nargs="+", help="chỉ hỏi các ca này (kho vẫn nạp đủ)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    limit = 2 if args.dry_run and not args.limit else args.limit
    controls = 2 if args.dry_run and args.controls is None else args.controls
    model = "gia-lap" if args.dry_run else str(config["llm_model"])
    run_dir = new_run_dir("tn6_kho_hoi_dap" + ("_dry" if args.dry_run else ""))
    print(f"== {config['ma']}: {config.get('ten', '')} — {model}")

    rows, extra = run_experiment(config, args.dry_run, limit, controls, args.ids)
    table = summarize(rows)
    write_csv(run_dir / "chi_tiet.csv", rows)
    text = report(config, model, table, extra)
    (run_dir / "tong_hop.md").write_text(text + "\n", encoding="utf-8")
    save_configs(
        run_dir, [config], {"mo_hinh": model, "dry_run": args.dry_run, "ids": args.ids, **extra}
    )
    print(text)
    print(f"\nKết quả: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
