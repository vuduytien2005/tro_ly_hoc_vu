"""loader + cleaner + chunker + keyword (không cần CSDL)."""

from pathlib import Path

import pytest

from src.rag import cleaner, loader
from src.rag.chunker import DocumentInfo, approx_token_count, chunk_document
from src.rag.keyword import KeywordIndex, tokenize
from src.rag.loader import Page, UnsupportedDocumentError
from tests.rag.conftest import SAMPLE

DOC = DocumentInfo("Quy chế đào tạo", "2023")


@pytest.fixture
def pages() -> list[Page]:
    return cleaner.clean_pages(loader.load(SAMPLE))


# --- cleaner --------------------------------------------------------------
def test_removes_repeated_header_and_page_numbers(pages: list[Page]) -> None:
    text = "\n".join(p.text for p in pages)
    assert "VĂN BẢN GIẢ LẬP" not in text
    assert "Trang 1" not in text and "Trang 3" not in text
    assert [p.number for p in pages] == [1, 2, 3]


def test_joins_broken_lines_but_keeps_structure(pages: list[Page]) -> None:
    lines = pages[1].text.split("\n")
    assert (
        "1. Đầu mỗi học kỳ, sinh viên đăng ký các học phần dự định học trong thời gian "
        "nhà trường quy định."
    ) in lines
    # câu dẫn chiếu "Điều 6 của Quy chế này" bị ngắt dòng được nối lại, không thành Điều mới
    assert any(line.endswith("theo quy định tại Điều 6 của Quy chế này.") for line in lines)
    assert "Điều 4. Học lại và học cải thiện điểm" in lines
    # không nối nội dung vào dòng tiêu đề Điều
    assert "Điều 3. Đăng ký học phần" in lines


def test_normalizes_unicode_to_nfc() -> None:
    nfd = "Học lại"  # "Học lại" dạng tổ hợp
    [page] = cleaner.clean_pages([Page(1, nfd)])
    assert page.text == "Học lại"


def test_short_document_keeps_edge_lines() -> None:
    """Ít hơn 3 trang thì không đoán header/footer (tránh xóa nhầm nội dung)."""
    out = cleaner.clean_pages(
        [Page(1, "Tiêu đề\nNội dung một."), Page(2, "Tiêu đề\nNội dung hai.")]
    )
    assert out[0].text.startswith("Tiêu đề")


# --- chunker theo_dieu ----------------------------------------------------
def test_one_chunk_per_article(pages: list[Page]) -> None:
    chunks, used = chunk_document(pages, DOC)
    assert used == "theo_dieu"
    articles = [c.dieu for c in chunks if c.dieu]
    assert articles == [
        "Điều 1. Phạm vi điều chỉnh",
        "Điều 2. Tín chỉ và học phần",
        "Điều 3. Đăng ký học phần",
        "Điều 4. Học lại và học cải thiện điểm",
        "Điều 5. Thang điểm",
        "Điều 6. Cảnh báo học vụ",
        "Điều 7. Điều kiện tốt nghiệp",
    ]
    assert chunks[0].dieu is None  # phần mở đầu (tên văn bản, căn cứ)
    assert [c.thu_tu for c in chunks] == list(range(1, len(chunks) + 1))


def test_chapter_page_and_prefix(pages: list[Page]) -> None:
    chunks, _ = chunk_document(pages, DOC)
    by_article = {c.dieu: c for c in chunks if c.dieu}
    retake = by_article["Điều 4. Học lại và học cải thiện điểm"]
    assert retake.chuong == "Chương II. TỔ CHỨC ĐÀO TẠO"
    assert retake.trang == 2
    assert retake.noi_dung.split("\n")[0] == (
        "Quy chế đào tạo (2023) – Chương II. TỔ CHỨC ĐÀO TẠO – "
        "Điều 4. Học lại và học cải thiện điểm"
    )
    assert "bị điểm F phải đăng ký học lại" in retake.noi_dung
    assert (
        by_article["Điều 7. Điều kiện tốt nghiệp"].chuong == "Chương III. ĐÁNH GIÁ KẾT QUẢ HỌC TẬP"
    )


def test_long_article_split_by_clause(pages: list[Page]) -> None:
    chunks, _ = chunk_document(pages, DOC, max_tokens=90)
    reg = [c for c in chunks if c.dieu == "Điều 3. Đăng ký học phần"]
    assert [c.khoan for c in reg] == ["1-2", "3"]
    assert all(c.so_token <= 90 for c in chunks)
    # mỗi phần vẫn mang tiền tố của Điều
    assert all(c.noi_dung.startswith("Quy chế đào tạo (2023) – Chương II") for c in reg)


def test_very_long_clause_uses_windows_within_budget(pages: list[Page]) -> None:
    chunks, _ = chunk_document(pages, DOC, max_tokens=60)
    assert all(c.so_token <= 60 for c in chunks)
    assert len(chunks) < 30


def test_falls_back_to_fixed_without_articles() -> None:
    notice = [Page(1, "THÔNG BÁO\n" + "Sinh viên nộp học phí trước ngày 15/10. " * 80)]
    chunks, used = chunk_document(notice, DocumentInfo("Thông báo học phí", "2026"))
    assert used == "co_dinh"
    assert len(chunks) >= 2
    assert all(c.dieu is None for c in chunks)
    assert all(c.so_token <= 420 for c in chunks)


def test_fixed_strategy_has_overlap(pages: list[Page]) -> None:
    long_pages = [Page(1, " ".join(f"từ{i}" for i in range(1000)))]
    chunks, used = chunk_document(long_pages, DOC, "co_dinh")
    assert used == "co_dinh"
    first = chunks[0].noi_dung.split("\n", 1)[1].split()
    second = chunks[1].noi_dung.split("\n", 1)[1].split()
    assert first[-1] in second  # đoạn sau bắt đầu trước khi đoạn trước kết thúc


def test_semantic_falls_back_to_articles(pages: list[Page]) -> None:
    _, used = chunk_document(pages, DOC, "ngu_nghia")
    assert used == "theo_dieu"


def test_invalid_strategy(pages: list[Page]) -> None:
    with pytest.raises(ValueError):
        chunk_document(pages, DOC, "khong_ton_tai")


def test_out_of_sequence_article_is_text() -> None:
    """'Điều 15.' xuất hiện sau Điều 1 (nhảy quá xa) -> coi là nội dung, không phải Điều mới."""
    text = (
        "Điều 1. Phạm vi\n1. Nội dung.\nĐiều 15. của luật khác được dẫn chiếu.\n"
        "Điều 2. Đối tượng\n1. A."
    )
    chunks, _ = chunk_document([Page(1, text)], DOC)
    assert [c.dieu for c in chunks] == ["Điều 1. Phạm vi", "Điều 2. Đối tượng"]


# --- loader ---------------------------------------------------------------
def test_load_docx(tmp_path: Path) -> None:
    from docx import Document

    doc = Document()
    doc.add_paragraph("Điều 1. Phạm vi điều chỉnh")
    doc.add_paragraph("1. Quy chế áp dụng cho sinh viên chính quy.")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Điểm chữ"
    table.rows[0].cells[1].text = "A"
    path = tmp_path / "a.docx"
    doc.save(str(path))

    [page] = loader.load(path)
    assert page.number == 1
    assert page.text.split("\n") == [
        "Điều 1. Phạm vi điều chỉnh",
        "1. Quy chế áp dụng cho sinh viên chính quy.",
        "Điểm chữ | A",
    ]


def test_load_pdf_keeps_page_numbers(tmp_path: Path) -> None:
    import pymupdf

    path = tmp_path / "a.pdf"
    with pymupdf.open() as doc:
        for text in ("Dieu 1. Pham vi", "Dieu 2. Doi tuong"):
            doc.new_page().insert_text((72, 72), text)
        doc.save(str(path))
    pages = loader.load(path)
    assert [p.number for p in pages] == [1, 2]
    assert "Dieu 2" in pages[1].text


def test_load_unsupported(tmp_path: Path) -> None:
    path = tmp_path / "a.xlsx"
    path.write_bytes(b"x")
    with pytest.raises(UnsupportedDocumentError):
        loader.load(path)


# --- BM25 -----------------------------------------------------------------
def test_tokenize_keeps_short_syllables_and_bigrams() -> None:
    tokens = tokenize("Nợ HỌC PHÍ kỳ này")
    assert {"nợ", "kỳ", "học", "học_phí", "nợ_học"} <= set(tokens)


def test_bm25_prefers_phrase_match() -> None:
    index = KeywordIndex(
        [
            (1, "Sinh viên phải học lại học phần bị điểm F."),
            (2, "Học phí được tính theo tín chỉ. Sinh viên nghỉ học thì xử lý lại hồ sơ."),
            (3, "Điều kiện tốt nghiệp gồm tín chỉ và điểm trung bình."),
        ]
    )
    results = index.search("học lại môn bị F")
    assert results[0][0] == 1
    assert 3 not in [doc_id for doc_id, _ in results]


def test_bm25_empty() -> None:
    assert KeywordIndex([]).search("học lại") == []


def test_approx_token_count() -> None:
    assert approx_token_count("một hai ba") == 5
