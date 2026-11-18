"""Đọc văn bản quy chế -> danh sách trang [(số trang, nội dung)].

- PDF: pymupdf, giữ số trang để trích dẫn ("trang 8").
- DOCX: python-docx (đoạn + bảng theo đúng thứ tự); DOCX không có khái niệm trang -> trang 1.
- TXT: tách trang bằng ký tự form feed (\\f) — dùng cho dữ liệu test.
"""

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}


@dataclass(frozen=True)
class Page:
    number: int
    text: str


class UnsupportedDocumentError(ValueError):
    pass


def load(path: Path) -> list[Page]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return _load_docx(path)
    if suffix == ".txt":
        return _load_txt(path)
    raise UnsupportedDocumentError(
        f"Không hỗ trợ định dạng '{suffix}' (chỉ nhận {', '.join(sorted(SUPPORTED_SUFFIXES))})."
    )


def _load_pdf(path: Path) -> list[Page]:
    import pymupdf

    pages: list[Page] = []
    with pymupdf.open(path) as doc:
        for index, page in enumerate(doc, start=1):
            # sort=True: đọc theo thứ tự trên -> dưới, trái -> phải (PDF scan/2 cột đỡ lộn xộn)
            pages.append(Page(index, page.get_text("text", sort=True)))
    if not any(p.text.strip() for p in pages):
        raise UnsupportedDocumentError(
            "PDF không có lớp chữ (có thể là bản scan ảnh). Cần OCR trước khi lập chỉ mục."
        )
    return pages


def _load_docx(path: Path) -> list[Page]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(path))
    lines: list[str] = []
    for block in doc.iter_inner_content():
        if isinstance(block, Paragraph):
            lines.append(block.text)
        elif isinstance(block, Table):
            for row in block.rows:
                cells = [c.text.strip() for c in row.cells]
                # ô gộp bị lặp lại trong python-docx -> bỏ trùng liên tiếp
                deduped = [c for i, c in enumerate(cells) if c and (i == 0 or c != cells[i - 1])]
                lines.append(" | ".join(deduped))
    return [Page(1, "\n".join(lines))]


def _load_txt(path: Path) -> list[Page]:
    text = path.read_text(encoding="utf-8-sig")
    return [Page(i, part) for i, part in enumerate(text.split("\f"), start=1)]
