"""Phần dùng chung cho các script thực nghiệm.

- `bootstrap()`: thêm backend/ vào sys.path để import `src.*` (chạy từ thư mục gốc dự án).
- Cấu hình: evaluation/configs/<mã>.yaml. Kết quả: evaluation/results/<YYYYMMDD-HHMM>_<tn>/
  gồm cấu hình đã dùng, chi_tiet.csv (từng câu), tong_hop.csv + bang.md (theo cấu hình), *.png.
"""

import csv
import json
import math
import shutil
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "evaluation"
CONFIG_DIR = EVAL_DIR / "configs"
DATASET_DIR = EVAL_DIR / "datasets"
RESULTS_DIR = EVAL_DIR / "results"
BACKEND = ROOT / "backend"


def bootstrap() -> None:
    for path in (str(BACKEND), str(ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)
    import os

    quiet_logs()
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    # Windows: in tiếng Việt ra console không lỗi mã hóa
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def quiet_logs() -> None:
    """Bớt log: mỗi kịch bản có hàng chục request nội bộ (TestClient, MCP, qlsv). Gọi lại sau khi
    dựng app vì một số thư viện cấu hình lại logging khi khởi tạo."""
    import logging

    for name in (
        "httpx",
        "httpx2",
        "mcp",
        "src.rag.retriever",
        "sentence_transformers",
        "LiteLLM",  # mỗi lượt gọi LLM in một dòng INFO "completion() model=..."
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


# ----- Cấu hình, dữ liệu -------------------------------------------------------
def load_config(name: str) -> dict[str, Any]:
    import yaml

    path = Path(name)
    if not path.suffix:
        path = CONFIG_DIR / f"{name}.yaml"
    with path.open(encoding="utf-8") as f:
        config: dict[str, Any] = yaml.safe_load(f) or {}
    config.setdefault("ma", path.stem)
    config["_tep"] = str(path)
    return config


def read_jsonl(path: Path | str, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{i}: JSON không hợp lệ ({exc.msg})") from exc
            if limit and len(rows) >= limit:
                break
    return rows


def dataset_path(config: dict[str, Any], default: str) -> Path:
    return ROOT / config.get("du_lieu", f"evaluation/datasets/{default}")


# ----- Kết quả -------------------------------------------------------------------
def new_run_dir(tn: str) -> Path:
    path = RESULTS_DIR / f"{datetime.now():%Y%m%d-%H%M}_{tn}"
    suffix = 1
    while path.exists():
        suffix += 1
        path = RESULTS_DIR / f"{datetime.now():%Y%m%d-%H%M}_{tn}_{suffix}"
    path.mkdir(parents=True)
    return path


def save_configs(run_dir: Path, configs: Iterable[dict[str, Any]], extra: dict[str, Any]) -> None:
    folder = run_dir / "cau_hinh"
    folder.mkdir(exist_ok=True)
    for c in configs:
        shutil.copy(c["_tep"], folder / Path(c["_tep"]).name)
    (run_dir / "lan_chay.json").write_text(
        json.dumps(extra, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


def _cell(value: Any) -> Any:
    if isinstance(value, float):
        return "" if math.isnan(value) else round(value, 4)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields: list[str] = []
    for row in rows:
        fields.extend(k for k in row if k not in fields)
    # utf-8-sig: Excel trên Windows mở đúng tiếng Việt
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: _cell(row.get(k)) for k in fields} for row in rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fmt(value: Any, percent: bool = False) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if isinstance(value, bool):
        return "✓" if value else "✗"
    if isinstance(value, float):
        if percent:
            return f"{value * 100:.1f}%"
        return f"{value:.3f}" if abs(value) < 10 else f"{value:,.1f}"
    return str(value)


def markdown_table(
    rows: Sequence[dict[str, Any]], columns: Sequence[tuple[str, str]], percent: Iterable[str] = ()
) -> str:
    pct = set(percent)
    head = "| " + " | ".join(label for _, label in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    body = [
        "| " + " | ".join(fmt(r.get(key), key in pct) for key, _ in columns) + " |" for r in rows
    ]
    return "\n".join([head, sep, *body])


def mean(values: Iterable[Any]) -> float:
    data = [
        float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))
    ]
    return sum(data) / len(data) if data else math.nan


# ----- Mô hình đã tải chưa ----------------------------------------------------------
def model_cached(model_name: str) -> bool:
    """Mô hình Hugging Face đã có trong cache máy chưa (tránh tự tải vài GB)."""
    from huggingface_hub import scan_cache_dir

    try:
        return any(repo.repo_id == model_name for repo in scan_cache_dir().repos)
    except Exception:
        return False


# ----- Reset dữ liệu QLSV ------------------------------------------------------------
def reset_qlsv() -> float:
    """Chạy backend/scripts/reset_demo.ps1 (tạo lại bảng + dữ liệu mẫu tlhv_qlsv). Trả số giây."""
    started = time.perf_counter()
    script = BACKEND / "scripts" / "reset_demo.ps1"
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ChiQlsv",
            "-Quiet",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Reset QLSV lỗi:\n{result.stdout}\n{result.stderr}")
    return time.perf_counter() - started


def progress(i: int, n: int, label: str) -> None:
    print(f"  [{i}/{n}] {label}", flush=True)
