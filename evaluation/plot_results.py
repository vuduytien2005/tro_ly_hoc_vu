"""Vẽ biểu đồ PNG từ tong_hop.csv của các lượt chạy (đặt cạnh bang.md trong thư mục kết quả).

    python evaluation\\plot_results.py                      # lượt chạy MỚI NHẤT của mỗi TN
    python evaluation\\plot_results.py evaluation\\results\\20261119-0917_tn2_tra_loi_dry

Màu: bảng màu phân loại cố định (xanh, cam, ngọc, vàng — đã kiểm tra mù màu), thứ tự cố định
theo chỉ số; "bị lọt" ở TN4 dùng màu trạng thái nguy hiểm. Giá trị ghi trên cột (các màu sáng
có độ tương phản thấp với nền nên không để màu mang nghĩa một mình).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.common import RESULTS_DIR, bootstrap, read_csv  # noqa: E402

bootstrap()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
CRITICAL = "#d03b3b"

plt.rcParams.update(
    {
        "font.family": ["Segoe UI", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_2,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "axes.titlecolor": INK,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
    }
)


def number(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def style(ax: plt.Axes, percent: bool = True) -> None:
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    if percent:
        ax.set_ylim(0, 1.12)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))


def grouped_bars(
    groups: list[str],
    series: list[tuple[str, list[float | None]]],
    title: str,
    path: Path,
    percent: bool = True,
) -> None:
    """Cột nhóm: mỗi nhóm (cấu hình) có một cột cho mỗi chỉ số; khe 2px giữa các cột."""
    n = len(series)
    width = min(0.8 / max(n, 1), 0.22)
    fig, ax = plt.subplots(figsize=(max(6.0, 1.3 * len(groups) * max(n, 2) * 0.45 + 2), 4.2))
    for i, (label, values) in enumerate(series):
        xs = [g + (i - (n - 1) / 2) * width for g in range(len(groups))]
        heights = [v if v is not None else 0 for v in values]
        bars = ax.bar(
            xs,
            heights,
            width,
            label=label,
            color=SERIES[i % len(SERIES)],
            edgecolor=SURFACE,
            linewidth=1.5,
        )
        for bar, v in zip(bars, values, strict=True):
            if v is None:
                continue
            text = f"{v * 100:.0f}%" if percent else f"{v:.2f}"
            ax.annotate(
                text,
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color=INK_2,
            )
    ax.set_xticks(range(len(groups)), groups)
    style(ax, percent)
    ax.set_title(title, loc="left", fontsize=12, pad=26)
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
        ncol=n,
        frameon=False,
        fontsize=9,
        handlelength=1.0,
        borderaxespad=0.2,
        labelcolor=INK_2,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_tn1(run: Path) -> Path:
    rows = [r for r in read_csv(run / "tong_hop.csv") if r["nhom"] == "tat_ca"]
    groups = [r["cau_hinh"] for r in rows]
    series = [
        (m.replace("hit", "Hit").replace("mrr", "MRR"), [number(r[m]) for r in rows])
        for m in ("hit@1", "hit@3", "hit@5", "mrr")
    ]
    out = run / "tn1_truy_xuat.png"
    grouped_bars(groups, series, "TN1 — Chất lượng truy xuất theo cấu hình", out)
    return out


def plot_tn2(run: Path) -> Path:
    rows = read_csv(run / "tong_hop.csv")
    groups = [r["nhom"] for r in rows]
    metrics = [
        ("faithfulness", "Faithfulness"),
        ("relevancy", "Relevancy"),
        ("faithfulness_menh_de", "F theo mệnh đề"),
        ("trich_dan_hop_le", "Trích dẫn hợp lệ"),
        ("trich_dung_nguon", "Trích đúng nguồn"),
        ("tu_choi_dung", "Từ chối đúng"),
    ]
    series = [(label, [number(r.get(key)) for r in rows]) for key, label in metrics]
    series = [s for s in series if any(v is not None for v in s[1])]
    out = run / "tn2_tra_loi.png"
    grouped_bars(groups, series, "TN2 — Chất lượng câu trả lời", out)
    return out


def plot_tn3(run: Path) -> Path:
    rows = read_csv(run / "tong_hop.csv")
    groups = [r["cau_hinh"] for r in rows]
    series = [
        (label, [number(r[key]) for r in rows])
        for key, label in (
            ("dung_cong_cu", "Đúng công cụ"),
            ("dung_tham_so", "Đúng tham số"),
            ("hoan_thanh", "Hoàn thành"),
        )
    ]
    out = run / "tn3_agent.png"
    grouped_bars(groups, series, "TN3 — Năng lực Agent theo cấu hình", out)
    return out


def plot_tn4(run: Path) -> Path:
    """Thanh ngang 100% theo nhóm tấn công: (a) LLM từ chối, (b) hệ thống chặn, bị lọt."""
    rows = read_csv(run / "tong_hop.csv")
    tiers = [
        ("llm_tu_choi", "(a) LLM tự từ chối", SERIES[0]),
        ("he_thong_chan", "(b) Hệ thống chặn", SERIES[2]),
        ("bi_lot", "Bị lọt", CRITICAL),
    ]
    labels = [f"{r['nhom']} (n={r['n']})" for r in rows]
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(rows) + 1.6))
    left = [0.0] * len(rows)
    for key, label, color in tiers:
        values = [number(r[key]) or 0 for r in rows]
        ax.barh(
            labels,
            values,
            left=left,
            color=color,
            label=label,
            edgecolor=SURFACE,
            linewidth=1.5,
            height=0.6,
        )
        for i, v in enumerate(values):
            if v >= 0.08:
                ax.text(
                    left[i] + v / 2,
                    i,
                    f"{v * 100:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if key != "he_thong_chan" else INK,
                )
        left = [a + b for a, b in zip(left, values, strict=True)]
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
    ax.tick_params(length=0)
    ax.set_title("TN4 — Kết quả an toàn theo nhóm tấn công", loc="left", fontsize=12, pad=26)
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
        ncol=3,
        frameon=False,
        fontsize=9,
        handlelength=1.0,
        borderaxespad=0.2,
        labelcolor=INK_2,
    )
    fig.tight_layout()
    out = run / "tn4_an_toan.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


PLOTTERS = {"tn1": plot_tn1, "tn2": plot_tn2, "tn3": plot_tn3, "tn4": plot_tn4}


def kind_of(run: Path) -> str | None:
    tag = run.name.split("_", 1)[1] if "_" in run.name else ""
    return next((k for k in PLOTTERS if tag.startswith(k)), None)


def latest_runs() -> list[Path]:
    runs: dict[str, Path] = {}
    for run in sorted(p for p in RESULTS_DIR.glob("*_tn*") if (p / "tong_hop.csv").exists()):
        kind = kind_of(run)
        if kind:
            runs[kind] = run  # tên thư mục bắt đầu bằng thời gian -> cái sau là mới nhất
    return [runs[k] for k in sorted(runs)]


def main() -> int:
    runs = [Path(a).resolve() for a in sys.argv[1:]] or latest_runs()
    if not runs:
        print("Chưa có kết quả nào trong evaluation/results/.")
        return 1
    for run in runs:
        kind = kind_of(run)
        if kind is None or not (run / "tong_hop.csv").exists():
            print(f"Bỏ qua {run}: không phải thư mục kết quả TN1–TN4")
            continue
        print(f"{kind.upper()}: {PLOTTERS[kind](run)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
