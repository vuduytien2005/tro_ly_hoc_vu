"""TN2 — Chất lượng câu trả lời RAG (trợ lý thật trả lời câu hỏi quy chế).

    python evaluation\\run_rag_answer.py --dry-run          # LLM giả + không chấm, miễn phí
    python evaluation\\run_rag_answer.py --limit 10
    python evaluation\\run_rag_answer.py --khong-cham       # chỉ chạy trợ lý, bỏ LLM chấm

Chỉ số:
- faithfulness, relevancy: LLM chấm (judge_model) thang 1–5, quy về 0–1 bằng (điểm-1)/4.
- trích dẫn hợp lệ: mọi [n] trong câu trả lời GỐC của LLM (trước hậu kiểm) đều có trong kết quả tra
  cứu của lượt -> đo LLM bịa trích dẫn; "bị hậu kiểm xóa" = số [n] bịa mà hệ thống đã xóa.
- trích đúng nguồn: có [n] trỏ tới văn bản + phiên bản + Điều đúng (với câu có nguồn đúng).
- từ chối đúng: câu "ngoai_pham_vi" phải trả lời là không tìm thấy (không bịa).
Chấm tay 30 câu: mở chi_tiet.csv, điền cột cham_tay (thang 0–2, docs/09) rồi so với LLM chấm.
"""

import argparse
import json
import re
import sys
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

from evaluation import metrics  # noqa: E402
from evaluation.harness import AgentHarness, cost_usd  # noqa: E402

# Tài khoản mẫu theo khóa (dữ liệu seed tlhv_qlsv)
STUDENT_OF_COHORT = {"K21": "SV21001", "K22": "SV22001", "K23": "SV23001"}

JUDGE_PROMPT = """Bạn là giám khảo đánh giá trợ lý tra cứu quy chế đào tạo. Chấm khách quan,
chỉ dựa vào dữ liệu dưới đây.

<cau_hoi>{question}</cau_hoi>
<dap_an_chuan>{reference}</dap_an_chuan>
<ngu_canh_truy_xuat>
{context}
</ngu_canh_truy_xuat>
<cau_tra_loi>{answer}</cau_tra_loi>

Tiêu chí (thang 1–5):
- faithfulness: mọi khẳng định trong câu trả lời đều có căn cứ trong ngữ cảnh truy xuất
  (5 = hoàn toàn có căn cứ; 1 = phần lớn bịa).
  Nếu câu trả lời chỉ nói không tìm thấy thông tin thì cho 5.
- relevancy: câu trả lời giải quyết đúng câu hỏi và khớp đáp án chuẩn
  (5 = đúng và đủ; 1 = sai/lạc đề).
  Nếu đáp án chuẩn nói văn bản không quy định thì câu trả lời đúng là nói không tìm thấy.

Chỉ trả về một đối tượng JSON, không thêm chữ nào khác:
{{"faithfulness": <1-5>, "relevancy": <1-5>, "ly_do": "<một câu ngắn>"}}"""


def _completion_with_wait(max_wait: float = 180.0, **params: Any) -> Any:
    """litellm.completion + chờ đúng thời gian nhà cung cấp yêu cầu khi gặp 429/503 (gói miễn phí,
    vd Gemini 15 lượt/phút). Hết hạn mức ngày (phải chờ quá lâu) thì báo lỗi luôn."""
    import time

    import litellm
    from src.assistant_api.agent.llm import retry_delay_seconds

    waited = 0.0
    while True:
        try:
            PACER.wait()
            return litellm.completion(**params)
        except (litellm.RateLimitError, litellm.ServiceUnavailableError) as exc:
            delay = retry_delay_seconds(exc)
            if waited + delay > max_wait:
                raise
            print(f"    (LLM chấm vượt hạn mức, chờ {delay:.0f}s)")
            time.sleep(delay)
            waited += delay


def judge(model: str, question: str, reference: str, context: str, answer: str) -> dict[str, Any]:

    prompt = JUDGE_PROMPT.format(
        question=question, reference=reference, context=context or "(không có)", answer=answer
    )
    response = _completion_with_wait(
        model=model, messages=[{"role": "user", "content": prompt}], max_tokens=2000
    )
    text = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    out: dict[str, Any] = {
        "token_vao": getattr(usage, "prompt_tokens", 0) or 0,
        "token_ra": getattr(usage, "completion_tokens", 0) or 0,
    }
    m = re.search(r"\{.*\}", text, re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
        out["faithfulness"] = (float(data["faithfulness"]) - 1) / 4
        out["relevancy"] = (float(data["relevancy"]) - 1) / 4
        out["ly_do"] = str(data.get("ly_do", ""))
    except (ValueError, KeyError, TypeError):
        out.update(faithfulness=None, relevancy=None, ly_do=f"Không đọc được JSON: {text[:200]}")
    return out


def sources_of(calls: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """Các đoạn search_regulations trả về trong lượt (đánh số [n]) + ngữ cảnh cho giám khảo."""
    found: list[dict[str, Any]] = []
    for c in calls:
        if c["ten_cong_cu"] == "search_regulations" and isinstance(c.get("ket_qua"), dict):
            found += [d for d in c["ket_qua"].get("doan") or [] if isinstance(d, dict)]
    context = "\n\n".join(f"[{d.get('so')}] {d.get('noi_dung', '')}" for d in found)
    return found, context


def evaluate(q: dict[str, Any], harness: AgentHarness, use_judge: bool) -> dict[str, Any]:
    ma_sv = STUDENT_OF_COHORT.get(q.get("ma_khoa") or "K22", "SV22001")
    out_of_scope = q.get("loai") == "ngoai_pham_vi"
    dry_text = (
        "Mình không tìm thấy thông tin này trong văn bản hiện có, em liên hệ phòng đào tạo nhé."
        if out_of_scope
        else f"{q.get('dap_an_chuan', '')} [1]"
    )
    harness.use_llm([("search_regulations", {"cau_hoi": q["cau_hoi"]})], dry_text)
    result = harness.run(ma_sv, q["cau_hoi"], auto_confirm=False)
    found, context = sources_of(result.calls)
    expected = q.get("nguon_dung") or []
    raw = result.raw_answer or result.last_answer
    raw_check = metrics.citation_check(raw, found, expected)
    stored_check = metrics.citation_check(result.last_answer, result.citations, expected)
    removed = len(metrics.cited_numbers(raw)) - len(metrics.cited_numbers(result.last_answer))

    row: dict[str, Any] = {
        "id": q["id"],
        "loai": q.get("loai"),
        "ma_khoa": q.get("ma_khoa"),
        "dang_nhap": ma_sv,
        "cau_hoi": q["cau_hoi"],
        "goi_tra_cuu": any(c["ten_cong_cu"] == "search_regulations" for c in result.llm_calls),
        "so_trich_dan": raw_check["so_trich_dan"],
        "trich_dan_hop_le": raw_check["hop_le"] if raw_check["so_trich_dan"] else None,
        "bi_hau_kiem_xoa": max(removed, 0),
        "trich_dung_nguon": stored_check["dung_nguon"],
        "tu_choi_dung": metrics.is_refusal(result.last_answer) if out_of_scope else None,
        "tu_choi_nham": metrics.is_refusal(result.last_answer) if not out_of_scope else None,
        "so_buoc": result.steps,
        "thoi_gian_s": round(result.seconds, 2),
        "token_vao": result.tokens_in,
        "token_ra": result.tokens_out,
        "faithfulness": None,
        "relevancy": None,
        "ly_do_cham": "",
        "cham_tay": "",
        "loi": result.error,
        "dap_an_chuan": q.get("dap_an_chuan"),
        "tra_loi": result.last_answer[:1500],
    }
    if use_judge and result.last_answer:
        verdict = judge(
            harness.config.get("judge_model") or harness.model,
            q["cau_hoi"],
            q.get("dap_an_chuan", ""),
            context,
            result.last_answer,
        )
        row.update(
            faithfulness=verdict["faithfulness"],
            relevancy=verdict["relevancy"],
            ly_do_cham=verdict["ly_do"],
            judge_token_vao=verdict["token_vao"],
            judge_token_ra=verdict["token_ra"],
        )
    return row


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    groups = [("tat_ca", rows)] + [
        (g, [r for r in rows if r["loai"] == g])
        for g in ("chung", "phu_thuoc_khoa", "ngoai_pham_vi")
    ]
    for name, items in groups:
        if not items:
            continue
        out.append(
            {
                "nhom": name,
                "n": len(items),
                "faithfulness": mean(r["faithfulness"] for r in items),
                "relevancy": mean(r["relevancy"] for r in items),
                "trich_dan_hop_le": mean(r["trich_dan_hop_le"] for r in items),
                "trich_dung_nguon": mean(r["trich_dung_nguon"] for r in items),
                "tu_choi_dung": mean(r["tu_choi_dung"] for r in items),
                "tu_choi_nham": mean(r["tu_choi_nham"] for r in items),
                "bi_hau_kiem_xoa": sum(r["bi_hau_kiem_xoa"] for r in items),
                "thoi_gian_tb_s": mean(r["thoi_gian_s"] for r in items),
            }
        )
    return out


COLUMNS = [
    ("nhom", "Nhóm"),
    ("n", "Số câu"),
    ("faithfulness", "Faithfulness"),
    ("relevancy", "Relevancy"),
    ("trich_dan_hop_le", "Trích dẫn hợp lệ"),
    ("trich_dung_nguon", "Trích đúng nguồn"),
    ("tu_choi_dung", "Từ chối đúng"),
    ("tu_choi_nham", "Từ chối nhầm"),
    ("bi_hau_kiem_xoa", "[n] bị xóa"),
    ("thoi_gian_tb_s", "TB (s)"),
]
PERCENT = {
    "faithfulness",
    "relevancy",
    "trich_dan_hop_le",
    "trich_dung_nguon",
    "tu_choi_dung",
    "tu_choi_nham",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="rag_answer")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--du-lieu", help="ghi đè tệp câu hỏi (.jsonl)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--khong-cham", action="store_true", help="không gọi LLM chấm")
    args = parser.parse_args()

    config = load_config(args.config)
    questions = read_jsonl(args.du_lieu or dataset_path(config, "rag_questions.jsonl"), args.limit)
    use_judge = not (args.dry_run or args.khong_cham)
    run_dir = new_run_dir("tn2_tra_loi" + ("_dry" if args.dry_run else ""))
    print(f"== {config['ma']}: {config.get('ten', '')} ({len(questions)} câu)")
    rows = []
    with AgentHarness(config, args.dry_run) as harness:
        for i, q in enumerate(questions, start=1):
            row = evaluate(q, harness, use_judge)
            rows.append(row)
            progress(
                i,
                len(questions),
                f"{q['id']} [{row['loai']}] F={metrics_fmt(row['faithfulness'])} "
                f"R={metrics_fmt(row['relevancy'])} trích dẫn={row['so_trich_dan']}"
                + (f" LỖI: {row['loi']}" if row["loi"] else ""),
            )
        tin = sum(r["token_vao"] for r in rows)
        tout = sum(r["token_ra"] for r in rows)
        cost = harness.cost(tin, tout)
    jin = sum(r.get("judge_token_vao", 0) for r in rows)
    jout = sum(r.get("judge_token_ra", 0) for r in rows)
    judge_cost = (
        cost_usd(config.get("judge_model") or config.get("llm_model", ""), jin, jout, config)
        if use_judge
        else 0.0
    )
    usage_text = (
        f"Trợ lý: token vào {tin:,} / ra {tout:,}; chấm: vào {jin:,} / ra {jout:,}. "
        f"Chi phí ước tính: trợ lý {money(cost)}, chấm {money(judge_cost)}."
    )
    print("  " + usage_text)

    summary = summarize(rows)
    write_csv(run_dir / "chi_tiet.csv", rows)
    write_csv(run_dir / "tong_hop.csv", summary)
    md = ["# TN2 — Chất lượng câu trả lời", ""]
    if args.dry_run:
        md += [
            "> CHẠY THỬ (--dry-run): LLM giả, không chấm — số liệu KHÔNG dùng cho khóa luận.",
            "",
        ]
    md += [markdown_table(summary, COLUMNS, PERCENT), "", usage_text, ""]
    (run_dir / "bang.md").write_text("\n".join(md), encoding="utf-8")
    save_configs(
        run_dir,
        [config],
        {"tn": "TN2", "dry_run": args.dry_run, "cham": use_judge, "limit": args.limit},
    )
    print("\n" + markdown_table(summary, COLUMNS, PERCENT))
    print(f"\nKết quả: {run_dir}")
    return 0


def metrics_fmt(value: Any) -> str:
    return "—" if value is None else f"{value:.2f}"


def money(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f} USD"


if __name__ == "__main__":
    raise SystemExit(main())
