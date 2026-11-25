"""TN5 — Kiểm chứng câu trả lời quy chế bằng LLM giám khảo (backend agent/verifier.py).

    python evaluation\\run_verifier.py --dry-run                 # LLM giả, 2 ca, miễn phí
    python evaluation\\run_verifier.py                           # cấu hình verifier (mặc định)
    python evaluation\\run_verifier.py --config verifier_gemini --limit 10

Mỗi ca (evaluation/datasets/verifier_cases.jsonl) có các đoạn quy chế THẬT trích từ corpus_demo,
một câu trả lời đúng và một biến thể cài đúng một ý sai (số liệu / thời hạn / điều kiện / nhầm
phiên bản 2021–2023). Giám khảo chấm cả hai câu trả lời. Chỉ số:
- recall (tỷ lệ bắt được): ý sai cài sẵn bị gắn "khong_co_can_cu";
- báo nhầm: câu trả lời ĐÚNG có ít nhất một ý bị gắn "khong_co_can_cu";
- thời gian, token thêm cho mỗi lần kiểm chứng (chi phí của tính năng).
Giám khảo lỗi / trả kết quả không đọc được -> ca đó tính là KHÔNG bắt được (cột loi ghi lý do).
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.common import (  # noqa: E402
    PACER,
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

CITATION_RE = r"\s*\[\d{1,3}\]"


def _core(text: str) -> str:
    import re

    return " ".join(re.sub(CITATION_RE, "", text).split()).strip(" .,;:!?").lower()


def flagged(result: dict[str, Any] | None, bad_sentence: str) -> bool:
    """Giám khảo có gắn "khong_co_can_cu" cho ý sai cài sẵn không (so khớp bỏ [n], khoảng trắng,
    dấu câu cuối; chấp nhận giám khảo trích một phần câu hoặc cả câu dài hơn)."""
    if not result:
        return False
    target = _core(bad_sentence)
    for claim in result.get("y", []):
        if claim.get("ket_luan") != "khong_co_can_cu":
            continue
        got = _core(str(claim.get("cau", "")))
        if got and (got in target or target in got):
            return True
    return False


def any_unsupported(result: dict[str, Any] | None) -> bool:
    return bool(result) and any(c.get("ket_luan") == "khong_co_can_cu" for c in result["y"])


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    return mean(1.0 if r[key] else 0.0 for r in rows)


def summarize(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(tổng hợp, theo loại lỗi)."""
    total = {
        "so_ca": len(rows),
        "recall": _rate(rows, "bat_duoc"),
        "bao_nham": _rate(rows, "bao_nham"),
        "thoi_gian_tb_ms": mean(r["thoi_gian_ms"] for r in rows),
        "token_vao_tb": mean(r["token_vao"] for r in rows),
        "token_ra_tb": mean(r["token_ra"] for r in rows),
        "so_loi": sum(1 for r in rows if r["loi"]),
    }
    by_kind = []
    for kind in sorted({r["loai_loi"] for r in rows}):
        items = [r for r in rows if r["loai_loi"] == kind]
        by_kind.append(
            {
                "loai_loi": kind,
                "so_ca": len(items),
                "recall": _rate(items, "bat_duoc"),
                "bao_nham": _rate(items, "bao_nham"),
            }
        )
    return total, by_kind


# ----- chạy -----------------------------------------------------------------------
def dry_run_llm(cases: list[dict[str, Any]]) -> Any:
    """LLM giả trả đúng thứ tự gọi: câu đúng -> mọi ý có căn cứ; câu sai -> ý cài sẵn bị gắn."""
    import json

    from src.assistant_api.agent.llm import FakeLLM, FakeResponse

    def verdict(answer: str, bad: str | None) -> FakeResponse:
        sentences = [s.strip() + "." for s in answer.split(".") if s.strip()]
        items = [
            {
                "cau": s,
                "ket_luan": "khong_co_can_cu" if bad and s == bad else "co_can_cu",
                "doan": [1],
                "ly_do": "giả lập",
            }
            for s in sentences
        ]
        return FakeResponse(text=json.dumps({"y": items}, ensure_ascii=False))

    responses = []
    for c in cases:
        responses += [verdict(c["tra_loi_dung"], None), verdict(c["tra_loi_sai"], c["y_sai"])]
    return FakeLLM(responses)


async def check(llm: Any, model: str, timeout: float, answer: str, passages: dict[int, str]):  # type: ignore[no-untyped-def]
    from src.assistant_api.agent.verifier import verify_answer

    waited = await PACER.await_turn()
    started = time.perf_counter()
    result, tin, tout = await verify_answer(
        llm, answer, passages, model_name=model, timeout=timeout
    )
    elapsed = int((time.perf_counter() - started) * 1000)
    return result, tin, tout, elapsed, waited


async def evaluate(case: dict[str, Any], llm: Any, model: str, timeout: float) -> dict[str, Any]:
    passages = {int(k): v for k, v in case["doan"].items()}
    good, gin, gout, gms, _ = await check(llm, model, timeout, case["tra_loi_dung"], passages)
    bad, bin_, bout, bms, _ = await check(llm, model, timeout, case["tra_loi_sai"], passages)
    errors = [name for name, r in (("dung", good), ("sai", bad)) if r is None]
    return {
        "id": case["id"],
        "loai_loi": case["loai_loi"],
        "bat_duoc": flagged(bad, case["y_sai"]),
        "bao_nham": any_unsupported(good),
        "thoi_gian_ms": (gms + bms) / 2,
        "token_vao": (gin + bin_) / 2,
        "token_ra": (gout + bout) / 2,
        "loi": ("giám khảo không trả kết quả: " + ", ".join(errors)) if errors else "",
        "y_sai": case["y_sai"],
        "ket_qua_sai": bad,
        "ket_qua_dung": good,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="verifier")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    limit = 2 if args.dry_run and not args.limit else args.limit
    cases = read_jsonl(dataset_path(config, "verifier_cases.jsonl"), limit)
    model = "gia-lap" if args.dry_run else str(config["verifier_model"])
    timeout = float(config.get("timeout_giay") or 60)
    PACER.min_interval = 0.0 if args.dry_run else float(config.get("cho_giua_luot_goi_giay") or 0)
    if args.dry_run:
        llm = dry_run_llm(cases)
    else:
        from src.assistant_api.agent.llm import LiteLlm

        llm = LiteLlm(model, timeout=timeout, num_ctx=config.get("llm_num_ctx"))

    run_dir = new_run_dir("tn5_kiem_chung" + ("_dry" if args.dry_run else ""))
    print(f"== {config['ma']}: {config.get('ten', '')} — {model} ({len(cases)} ca)")
    rows = []
    for i, case in enumerate(cases, start=1):
        row = asyncio.run(evaluate(case, llm, model, timeout))
        rows.append(row)
        progress(
            i,
            len(cases),
            f"{case['id']} [{case['loai_loi']}] bắt được={row['bat_duoc']} "
            f"báo nhầm={row['bao_nham']} {row['thoi_gian_ms']:.0f} ms"
            + (f" LỖI: {row['loi']}" if row["loi"] else ""),
        )

    total, by_kind = summarize(rows)
    write_csv(run_dir / "chi_tiet.csv", rows)
    columns = [
        ("so_ca", "Số ca"),
        ("recall", "Bắt được ý sai"),
        ("bao_nham", "Báo nhầm câu đúng"),
        ("thoi_gian_tb_ms", "Thời gian TB (ms)"),
        ("token_vao_tb", "Token vào TB"),
        ("token_ra_tb", "Token ra TB"),
        ("so_loi", "Lỗi giám khảo"),
    ]
    report = "\n\n".join(
        [
            f"# TN5 — Kiểm chứng câu trả lời ({config['ma']}, {model})",
            markdown_table([total], columns, percent=("recall", "bao_nham")),
            "## Theo loại lỗi cài sẵn",
            markdown_table(
                by_kind,
                [
                    ("loai_loi", "Loại lỗi"),
                    ("so_ca", "Số ca"),
                    ("recall", "Bắt được"),
                    ("bao_nham", "Báo nhầm"),
                ],
                percent=("recall", "bao_nham"),
            ),
        ]
    )
    (run_dir / "tong_hop.md").write_text(report + "\n", encoding="utf-8")
    save_configs(run_dir, [config], {"mo_hinh": model, "dry_run": args.dry_run, **total})
    print(report)
    print(f"\nKết quả: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
