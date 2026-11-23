"""Đối chiếu chấm tay với LLM chấm (TN2) — kiểm chứng giám khảo LLM có đáng tin không.

    python evaluation\\doi_chieu_cham_tay.py evaluation\\results\\<thư mục tn2_tra_loi>

Trước khi chạy: mở chi_tiet.csv của lần chạy TN2, điền cột `cham_tay` (người 1) và nếu có thì
`cham_tay_2` (người 2) cho ~30 câu, thang (docs/09):
    0 = sai / bịa / lạc đề; 1 = đúng một phần hoặc thiếu ý; 2 = đúng, đủ, có căn cứ.
Ô để trống = câu không chấm tay.

Kết quả (in ra + ghi doi_chieu.md trong thư mục đó), với từng người chấm so với từng điểm tự động
(relevancy, faithfulness 1–5, faithfulness theo mệnh đề):
- trùng khớp: tỉ lệ câu mà điểm tự động (quy về 0/1/2 bằng ba khoảng đều) bằng điểm tay;
- sai lệch TB: |điểm tay/2 − điểm tự động| trung bình (thang 0–1);
- Spearman: tương quan hạng (giám khảo xếp câu tốt/xấu có cùng thứ tự với người không).
Có hai người chấm -> thêm mức đồng thuận giữa hai người (trần hợp lý cho giám khảo LLM).
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation import metrics  # noqa: E402
from evaluation.common import fmt, read_csv  # noqa: E402

RATERS = (("cham_tay", "Người chấm 1"), ("cham_tay_2", "Người chấm 2"))
AUTO = (
    ("relevancy", "Relevancy (LLM 1–5)"),
    ("faithfulness", "Faithfulness (LLM 1–5)"),
    ("faithfulness_menh_de", "Faithfulness theo mệnh đề"),
)


def manual_score(value: str | None) -> int | None:
    value = (value or "").strip()
    if value in {"0", "1", "2"}:
        return int(value)
    if value:
        raise ValueError(f"Điểm chấm tay phải là 0, 1 hoặc 2 (gặp {value!r}).")
    return None


def auto_score(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def compare(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    table: list[dict[str, Any]] = []
    for col, rater in RATERS:
        for key, label in AUTO:
            pairs = [
                (m, a)
                for r in rows
                if (m := manual_score(r.get(col))) is not None
                and (a := auto_score(r.get(key))) is not None
            ]
            if pairs:
                table.append(
                    {"nguoi_cham": rater, "diem_tu_dong": label} | (metrics.manual_agreement(pairs))
                )
    both = [
        (m1, m2)
        for r in rows
        if (m1 := manual_score(r.get("cham_tay"))) is not None
        and (m2 := manual_score(r.get("cham_tay_2"))) is not None
    ]
    between = None
    if both:
        between = {
            "n": len(both),
            "trung_khop": sum(a == b for a, b in both) / len(both),
            "spearman": metrics.spearman([float(a) for a, _ in both], [float(b) for _, b in both]),
        }
    return table, between


def render(table: list[dict[str, Any]], between: dict[str, Any] | None) -> str:
    lines = [
        "# Đối chiếu chấm tay với LLM chấm (TN2)",
        "",
        "| Người chấm | Điểm tự động | Số câu | Trùng khớp (0/1/2) | Sai lệch TB | Spearman |",
        "|---|---|---|---|---|---|",
    ]
    for t in table:
        lines.append(
            f"| {t['nguoi_cham']} | {t['diem_tu_dong']} | {t['n']} | "
            f"{fmt(t['trung_khop'], percent=True)} | {fmt(t['sai_lech_tb'])} | "
            f"{fmt(t['spearman'])} |"
        )
    if between:
        lines += [
            "",
            f"Đồng thuận giữa hai người chấm ({between['n']} câu): trùng khớp "
            f"{fmt(between['trung_khop'], percent=True)}, Spearman {fmt(between['spearman'])}.",
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    run_dir = Path(sys.argv[1])
    path = run_dir / "chi_tiet.csv"
    if not path.exists():
        print(f"Không thấy {path}")
        return 1
    try:
        table, between = compare(read_csv(path))
    except ValueError as exc:
        print(exc)
        return 1
    if not table:
        print("Chưa có câu nào được chấm tay (cột cham_tay trống).")
        return 1
    text = render(table, between)
    (run_dir / "doi_chieu.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"Đã ghi {run_dir / 'doi_chieu.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
