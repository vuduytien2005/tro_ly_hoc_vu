"""TN3 — Năng lực Agent: đúng công cụ, đúng tham số, hoàn thành nhiệm vụ, số bước, độ trễ,
token, chi phí. Chạy từ thư mục gốc dự án, venv backend đã kích hoạt:

    python evaluation\\run_agent.py --dry-run   # LLM giả, miễn phí
    python evaluation\\run_agent.py --configs agent_opus --limit 10
    python evaluation\\run_agent.py --configs agent_opus agent_haiku agent_opus_toi_gian

So sánh mô hình (agent_opus vs agent_haiku) và mô tả công cụ (day_du vs toi_gian).
--dry-run: LLM giả gọi ĐÚNG công cụ mong đợi -> kiểm tra toàn bộ đường ống (kỳ vọng ~100%), không
dùng số liệu này cho khóa luận.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.common import (  # noqa: E402
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
from evaluation.harness import AgentHarness  # noqa: E402

DEFAULT_CONFIGS = ["agent_opus"]


def dry_steps(case: dict[str, Any], harness: AgentHarness) -> tuple[list, str]:
    expected = case.get("tham_so_mong_doi") or {}
    tools = case.get("cong_cu_mong_doi") or []
    nested = all(k in tools and isinstance(v, dict) for k, v in expected.items()) and expected
    steps = []
    for i, tool in enumerate(tools):
        if nested:
            args = dict(expected.get(tool) or {})
        else:  # dạng phẳng: áp cho công cụ cuối (bước thao tác chính)
            args = dict(expected) if i == len(tools) - 1 else {}
        args = {k: v for k, v in args.items() if k not in ("ma_sv", "ma_khoa")}
        steps.append((tool, harness.fill_required(tool, args, case["yeu_cau"])))
    want = case.get("ket_qua_mong_doi")
    text = want[0] if isinstance(want, list) else "Mình đã xử lý yêu cầu của em."
    return steps, text


def evaluate(case: dict[str, Any], harness: AgentHarness) -> dict[str, Any]:
    steps, text = dry_steps(case, harness)
    harness.use_llm(steps, text)
    result = harness.run(case["dang_nhap"], case["yeu_cau"], bool(case.get("tu_dong_xac_nhan")))
    llm_calls = result.llm_calls
    called = [c["ten_cong_cu"] for c in llm_calls]
    selection = metrics.tool_selection(
        called, case.get("cong_cu_mong_doi") or [], case.get("cong_cu_chap_nhan_them") or []
    )
    params_ok = metrics.params_match(
        llm_calls, case.get("tham_so_mong_doi") or {}, case.get("cong_cu_mong_doi") or []
    )
    done = metrics.task_completed(case, result.answer, result.calls, harness.write_tools)
    card_ok = (not case.get("can_xac_nhan")) or bool(result.pending)
    return {
        "cau_hinh": harness.config["ma"],
        "id": case["id"],
        "dang_nhap": case["dang_nhap"],
        "yeu_cau": case["yeu_cau"],
        "dung_cong_cu": selection["dung_tap_cong_cu"],
        "du_cong_cu": selection["du_cong_cu"],
        "thua": selection["thua"],
        "thieu": selection["thieu"],
        "dung_tham_so": params_ok,
        "hoan_thanh": done and card_ok,
        "co_the_xac_nhan": bool(result.pending),
        "so_buoc": result.steps,
        "thoi_gian_s": round(result.seconds, 2),
        "token_vao": result.tokens_in,
        "token_ra": result.tokens_out,
        "chi_phi_usd": harness.cost(result.tokens_in, result.tokens_out),
        "cong_cu_da_goi": [f"{c['ten_cong_cu']}:{c['trang_thai']}" for c in result.calls],
        "loi": result.error,
        "tra_loi": result.answer[:1000],
    }


def summarize(config: dict[str, Any], rows: list[dict[str, Any]], usage: dict[str, Any]) -> dict:
    seconds = [r["thoi_gian_s"] for r in rows]
    return {
        "cau_hinh": config["ma"],
        "mo_ta": config.get("ten", ""),
        "n": len(rows),
        "dung_cong_cu": mean(r["dung_cong_cu"] for r in rows),
        "du_cong_cu": mean(r["du_cong_cu"] for r in rows),
        "dung_tham_so": mean(r["dung_tham_so"] for r in rows),
        "hoan_thanh": mean(r["hoan_thanh"] for r in rows),
        "so_buoc_tb": mean(r["so_buoc"] for r in rows),
        "do_tre_trung_vi_s": metrics.percentile(seconds, 50),
        "do_tre_p95_s": metrics.percentile(seconds, 95),
        "token_tb": mean(r["token_vao"] + r["token_ra"] for r in rows),
        "chi_phi_usd": usage["chi_phi_usd"],
        "chi_phi_tb_usd": (usage["chi_phi_usd"] / len(rows))
        if usage["chi_phi_usd"] is not None and rows
        else None,
    }


COLUMNS = [
    ("cau_hinh", "Cấu hình"),
    ("n", "Số KB"),
    ("dung_cong_cu", "Đúng công cụ"),
    ("dung_tham_so", "Đúng tham số"),
    ("hoan_thanh", "Hoàn thành"),
    ("so_buoc_tb", "Bước TB"),
    ("do_tre_trung_vi_s", "Trễ trung vị (s)"),
    ("do_tre_p95_s", "Trễ P95 (s)"),
    ("token_tb", "Token TB"),
    ("chi_phi_tb_usd", "Chi phí TB (USD)"),
    ("chi_phi_usd", "Tổng (USD)"),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--configs", nargs="+", default=DEFAULT_CONFIGS)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--du-lieu", help="ghi đè tệp kịch bản (.jsonl)")
    parser.add_argument(
        "--dry-run", action="store_true", help="LLM giả (miễn phí), embedding hashing"
    )
    args = parser.parse_args()

    configs = [load_config(c) for c in args.configs]
    run_dir = new_run_dir("tn3_agent" + ("_dry" if args.dry_run else ""))
    all_rows: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for c in configs:
        cases = read_jsonl(args.du_lieu or dataset_path(c, "agent_scenarios.jsonl"), args.limit)
        print(f"\n== {c['ma']}: {c.get('ten', '')} ({len(cases)} kịch bản)")
        with AgentHarness(c, args.dry_run) as harness:
            rows = []
            results_usage = []
            for i, case in enumerate(cases, start=1):
                row = evaluate(case, harness)
                rows.append(row)
                results_usage.append((row["token_vao"], row["token_ra"], row["so_buoc"]))
                flag = "✓" if row["hoan_thanh"] else "✗"
                progress(
                    i,
                    len(cases),
                    f"{case['id']} {flag} {row['cong_cu_da_goi']}"
                    + (f" LỖI: {row['loi']}" if row["loi"] else ""),
                )
            tin = sum(t[0] for t in results_usage)
            tout = sum(t[1] for t in results_usage)
            usage = {"chi_phi_usd": harness.cost(tin, tout), "token_vao": tin, "token_ra": tout}
            cost = usage["chi_phi_usd"]
            cost_text = "—" if cost is None else f"{cost:.4f} USD"
            print(f"  Token: vào {tin:,} / ra {tout:,} — chi phí ước tính {cost_text}")
        all_rows += rows
        summary.append(summarize(c, rows, usage))

    write_csv(run_dir / "chi_tiet.csv", all_rows)
    write_csv(run_dir / "tong_hop.csv", summary)
    pct = {"dung_cong_cu", "dung_tham_so", "hoan_thanh"}
    md = ["# TN3 — Năng lực Agent", ""]
    if args.dry_run:
        md += [
            "> CHẠY THỬ (--dry-run): LLM giả gọi đúng công cụ mong đợi — "
            "số liệu KHÔNG dùng cho khóa luận.",
            "",
        ]
    md += [
        markdown_table(summary, COLUMNS, pct),
        "",
        "Chi phí ước tính theo bảng giá của LiteLLM (hoặc giá ghi đè trong cấu hình).",
        "",
    ]
    (run_dir / "bang.md").write_text("\n".join(md), encoding="utf-8")
    save_configs(run_dir, configs, {"tn": "TN3", "dry_run": args.dry_run, "limit": args.limit})
    print("\n" + markdown_table(summary, COLUMNS, pct))
    print(f"\nKết quả: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
