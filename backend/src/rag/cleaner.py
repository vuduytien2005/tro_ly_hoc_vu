"""Làm sạch văn bản trích từ PDF/DOCX trước khi chia đoạn.

1. Chuẩn hóa Unicode NFC (PDF tiếng Việt hay ở dạng tổ hợp NFD -> tìm kiếm sai).
2. Bỏ header/footer lặp lại: dòng đầu/cuối trang xuất hiện ở >= 50% số trang (so sánh sau khi
   thay chữ số bằng '#', để "Trang 3" và "Trang 4" được coi là một).
3. Bỏ dòng chỉ chứa số trang ("12", "- 12 -", "Trang 12", "12/30").
4. Ghép dòng bị ngắt giữa câu, NHƯNG không ghép vào/qua các dòng cấu trúc
   (Chương, Điều, khoản "1.", điểm "a)", gạch đầu dòng).
"""

import re
import unicodedata
from collections import Counter

from src.rag.loader import Page

EDGE_LINES = 2  # số dòng đầu/cuối mỗi trang được xét là header/footer

PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:trang\s*)?[-–—]?\s*\d{1,4}\s*(?:/\s*\d{1,4})?\s*[-–—]?\s*$", re.IGNORECASE
)
CHAPTER_LINE_RE = re.compile(r"^\s*chương\s+([ivxlc]+|\d+)\b", re.IGNORECASE)
ARTICLE_LINE_RE = re.compile(r"^\s*điều\s+\d+\s*[.:]", re.IGNORECASE)
# Dòng mở đầu một ý mới: khoản "1.", điểm "a)", "đ)", gạch đầu dòng
STRUCTURAL_START_RE = re.compile(r"^\s*(?:\d{1,2}[.)]\s|[a-zđ]\)\s|[-–+•*]\s)", re.IGNORECASE)
SENTENCE_END = (".", ":", ";", "!", "?", "…")
SPACES_RE = re.compile(r"[ \t ]+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("­", "").replace("\r\n", "\n").replace("\r", "\n")
    return text


def _signature(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def _repeated_edges(pages: list[list[str]]) -> set[str]:
    if len(pages) < 3:
        return set()
    counter: Counter[str] = Counter()
    for lines in pages:
        edges = {_signature(line) for line in lines[:EDGE_LINES] + lines[-EDGE_LINES:]}
        counter.update(s for s in edges if s)
    threshold = max(2, len(pages) // 2)
    return {sig for sig, n in counter.items() if n >= threshold}


def is_structural(line: str) -> bool:
    return bool(
        CHAPTER_LINE_RE.match(line)
        or ARTICLE_LINE_RE.match(line)
        or STRUCTURAL_START_RE.match(line)
    )


def _join_broken_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if not line:
            out.append("")
            continue
        prev = out[-1] if out else ""
        can_join = (
            prev
            and not prev.endswith(SENTENCE_END)
            and not is_structural(line)
            # không nối nội dung vào dòng tiêu đề Chương/Điều
            and not CHAPTER_LINE_RE.match(prev)
            and not ARTICLE_LINE_RE.match(prev)
            # không nối 2 dòng TIÊU ĐỀ IN HOA với dòng thường (vd tên chương -> Điều)
            and not (prev.isupper() and not line.isupper())
        )
        if can_join:
            out[-1] = f"{prev} {line}"
        else:
            out.append(line)
    # gộp nhiều dòng trống liên tiếp
    result: list[str] = []
    for line in out:
        if line or (result and result[-1]):
            result.append(line)
    return result


def clean_pages(pages: list[Page]) -> list[Page]:
    split = [
        [SPACES_RE.sub(" ", line).strip() for line in normalize(p.text).split("\n")] for p in pages
    ]
    split = [[line for line in lines if line] for lines in split]
    repeated = _repeated_edges(split)

    cleaned: list[Page] = []
    for page, lines in zip(pages, split, strict=True):
        kept = []
        for i, line in enumerate(lines):
            at_edge = i < EDGE_LINES or i >= len(lines) - EDGE_LINES
            if at_edge and _signature(line) in repeated:
                continue
            if PAGE_NUMBER_RE.match(line):
                continue
            kept.append(line)
        cleaned.append(Page(page.number, "\n".join(_join_broken_lines(kept))))
    return cleaned
