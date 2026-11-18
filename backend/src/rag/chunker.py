"""Chia văn bản đã làm sạch thành các đoạn (chunk) để lập chỉ mục.

Chiến lược (cột van_ban.chien_luoc_chunk):
- `theo_dieu` (mặc định): mỗi Điều là 1 đoạn; Điều dài hơn `max_tokens` thì gom các Khoản liên tiếp
  thành nhiều đoạn (Khoản quá dài thì cắt cửa sổ cố định). Phần trước Điều đầu tiên (tên văn bản,
  căn cứ ban hành) chia theo `co_dinh`.
- `co_dinh`: cửa sổ ~400 token, chồng lấn ~60 token — mốc so sánh (baseline).
- `ngu_nghia`: để Giai đoạn 8 (thực nghiệm); hiện rơi về `theo_dieu`.
Văn bản không nhận diện được Điều nào -> tự động dùng `co_dinh`.

Mọi đoạn có tiền tố ngữ cảnh ở dòng đầu: "{tên văn bản} ({phiên bản}) – {chương} – {điều}",
giúp cả embedding lẫn BM25 biết đoạn thuộc văn bản/Điều nào.

Nhận diện Điều chống nhầm với câu dẫn chiếu ("Điều 5 của Quy chế này" bị ngắt dòng): tiêu đề phải
có dạng "Điều <số>." / "Điều <số>:" và số Điều phải tăng dần (lớn hơn Điều trước tối đa 3).
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from src.rag.loader import Page

logger = logging.getLogger(__name__)

TokenCounter = Callable[[str], int]

STRATEGIES = ("theo_dieu", "co_dinh", "ngu_nghia")
FIXED_WINDOW_TOKENS = 400
FIXED_OVERLAP_TOKENS = 60
MAX_ARTICLE_GAP = 3

CHAPTER_RE = re.compile(r"^chương\s+([IVXLC]+|\d+)\b\s*[.:–-]?\s*(.*)$", re.IGNORECASE)
ARTICLE_RE = re.compile(r"^điều\s+(\d+)\s*[.:]\s*(.*)$", re.IGNORECASE)
CLAUSE_RE = re.compile(r"^(\d{1,2})\.\s+\S")


def approx_token_count(text: str) -> int:
    """Ước lượng token khi không nạp tokenizer (test). Tokenizer XLM-R (e5, bge-m3) tách
    tiếng Việt khoảng 1.3–1.5 token/âm tiết."""
    return int(len(text.split()) * 1.4) + 1


@dataclass(frozen=True)
class DocumentInfo:
    ten: str
    phien_ban: str


@dataclass
class Chunk:
    thu_tu: int
    noi_dung: str  # đã có dòng tiền tố ngữ cảnh
    trang: int | None
    so_token: int
    chuong: str | None = None
    dieu: str | None = None
    khoan: str | None = None


@dataclass
class _Line:
    text: str
    page: int
    chuong: str | None
    dieu: str | None


@dataclass
class _Article:
    title: str  # "Điều 12. Đăng ký học phần"
    chuong: str | None
    lines: list[_Line] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Phân tích cấu trúc
# ---------------------------------------------------------------------------
def _parse(pages: list[Page]) -> tuple[list[_Line], list[_Line], list[_Article]]:
    """Trả về (tất cả dòng có gắn chương/điều, phần mở đầu, danh sách Điều)."""
    all_lines: list[_Line] = []
    preamble: list[_Line] = []
    articles: list[_Article] = []
    chapter: str | None = None
    pending_chapter_title = False
    last_article_no = 0

    for page in pages:
        for raw in page.text.split("\n"):
            text = raw.strip()
            if not text:
                continue

            m_chapter = CHAPTER_RE.match(text)
            if m_chapter:
                title = m_chapter.group(2).strip()
                chapter = f"Chương {m_chapter.group(1).upper()}" + (f". {title}" if title else "")
                pending_chapter_title = not title
                all_lines.append(_Line(text, page.number, chapter, None))
                continue

            m_article = ARTICLE_RE.match(text)
            if m_article:
                number = int(m_article.group(1))
                if last_article_no < number <= last_article_no + MAX_ARTICLE_GAP:
                    last_article_no = number
                    pending_chapter_title = False
                    title = m_article.group(2).strip()
                    articles.append(
                        _Article(
                            title=f"Điều {number}." + (f" {title}" if title else ""), chuong=chapter
                        )
                    )

            if pending_chapter_title and not m_article and text.isupper():
                # "CHƯƠNG II" xuống dòng "TỔ CHỨC ĐÀO TẠO": dòng tên chương không thuộc Điều nào
                chapter = f"{chapter}. {text}"
                pending_chapter_title = False
                all_lines.append(_Line(text, page.number, chapter, None))
                continue
            pending_chapter_title = False

            if articles:
                line = _Line(text, page.number, articles[-1].chuong, articles[-1].title)
                articles[-1].lines.append(line)
            else:
                line = _Line(text, page.number, chapter, None)
                preamble.append(line)
            all_lines.append(line)
    return all_lines, preamble, articles


def _prefix(doc: DocumentInfo, chuong: str | None, dieu: str | None) -> str:
    parts = [f"{doc.ten} ({doc.phien_ban})"]
    parts += [p for p in (chuong, dieu) if p]
    return " – ".join(parts)


# ---------------------------------------------------------------------------
# Chiến lược co_dinh
# ---------------------------------------------------------------------------
def _fixed_windows(
    lines: list[_Line],
    doc: DocumentInfo,
    count_tokens: TokenCounter,
    window: int,
    overlap: int,
    khoan: str | None = None,
) -> list[Chunk]:
    words: list[tuple[str, _Line]] = [(w, line) for line in lines for w in line.text.split()]
    if not words:
        return []
    total_tokens = count_tokens(" ".join(w for w, _ in words))
    ratio = max(total_tokens / len(words), 0.1)  # token / từ
    window_words = max(int(window / ratio), 5)
    # chồng lấn không vượt 1/4 cửa sổ (cửa sổ nhỏ khi cắt Khoản dài)
    overlap_words = min(int(overlap / ratio), window_words // 4)
    step = window_words - overlap_words

    chunks: list[Chunk] = []
    start = 0
    while start < len(words):
        part = words[start : start + window_words]
        first = part[0][1]
        body = " ".join(w for w, _ in part)
        content = f"{_prefix(doc, first.chuong, first.dieu)}\n{body}"
        chunks.append(
            Chunk(
                thu_tu=0,
                noi_dung=content,
                trang=first.page,
                so_token=count_tokens(content),
                chuong=first.chuong,
                dieu=first.dieu,
                khoan=khoan,
            )
        )
        if start + window_words >= len(words):
            break
        start += step
    return chunks


# ---------------------------------------------------------------------------
# Chiến lược theo_dieu
# ---------------------------------------------------------------------------
def _split_clauses(article: _Article) -> list[tuple[str | None, list[_Line]]]:
    """[(số khoản | None cho phần dẫn trước khoản 1, các dòng)]; dòng tiêu đề Điều bị bỏ
    (đã có trong tiền tố)."""
    groups: list[tuple[str | None, list[_Line]]] = [(None, [])]
    expected = 1
    for line in article.lines[1:]:
        m = CLAUSE_RE.match(line.text)
        if m and int(m.group(1)) == expected:
            groups.append((m.group(1), [line]))
            expected += 1
        else:
            groups[-1][1].append(line)
    return [(k, ls) for k, ls in groups if ls]


def _khoan_label(numbers: list[str | None]) -> str | None:
    nums = [n for n in numbers if n]
    if not nums:
        return None
    return nums[0] if len(nums) == 1 else f"{nums[0]}-{nums[-1]}"


def _chunk_article(
    article: _Article, doc: DocumentInfo, count_tokens: TokenCounter, max_tokens: int
) -> list[Chunk]:
    prefix = _prefix(doc, article.chuong, article.title)
    whole = "\n".join(line.text for line in article.lines)
    content = f"{prefix}\n{whole}"
    tokens = count_tokens(content)
    page = article.lines[0].page
    if tokens <= max_tokens:
        return [Chunk(0, content, page, tokens, article.chuong, article.title)]

    # Điều quá dài: gom các Khoản liên tiếp sao cho mỗi đoạn <= max_tokens
    budget = max_tokens - count_tokens(prefix)
    chunks: list[Chunk] = []
    buf_lines: list[_Line] = []
    buf_nums: list[str | None] = []

    def flush() -> None:
        if not buf_lines:
            return
        body = "\n".join(line.text for line in buf_lines)
        text = f"{prefix}\n{body}"
        chunks.append(
            Chunk(
                0,
                text,
                buf_lines[0].page,
                count_tokens(text),
                article.chuong,
                article.title,
                _khoan_label(buf_nums),
            )
        )
        buf_lines.clear()
        buf_nums.clear()

    for number, lines in _split_clauses(article):
        clause_tokens = count_tokens("\n".join(line.text for line in lines))
        if clause_tokens > budget:
            flush()
            chunks.extend(
                _fixed_windows(lines, doc, count_tokens, budget, FIXED_OVERLAP_TOKENS, khoan=number)
            )
            continue
        current = count_tokens("\n".join(line.text for line in buf_lines)) if buf_lines else 0
        if buf_lines and current + clause_tokens > budget:
            flush()
        buf_lines.extend(lines)
        buf_nums.append(number)
    flush()
    return chunks


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def chunk_document(
    pages: list[Page],
    doc: DocumentInfo,
    strategy: str = "theo_dieu",
    *,
    max_tokens: int = 512,
    count_tokens: TokenCounter = approx_token_count,
) -> tuple[list[Chunk], str]:
    """Chia đoạn. Trả về (các đoạn đã đánh thu_tu từ 1, chiến lược thực sự đã dùng)."""
    if strategy not in STRATEGIES:
        raise ValueError(f"Chiến lược chia đoạn không hợp lệ: {strategy}")
    if strategy == "ngu_nghia":
        logger.warning("Chiến lược 'ngu_nghia' chưa cài đặt (Giai đoạn 8) -> dùng 'theo_dieu'.")
        strategy = "theo_dieu"

    all_lines, preamble, articles = _parse(pages)
    window = min(FIXED_WINDOW_TOKENS, max_tokens)

    if strategy == "theo_dieu" and articles:
        chunks = _fixed_windows(preamble, doc, count_tokens, window, FIXED_OVERLAP_TOKENS)
        for article in articles:
            chunks.extend(_chunk_article(article, doc, count_tokens, max_tokens))
        used = "theo_dieu"
    else:
        if strategy == "theo_dieu":
            logger.info("Không nhận diện được Điều nào trong '%s' -> dùng 'co_dinh'.", doc.ten)
        chunks = _fixed_windows(all_lines, doc, count_tokens, window, FIXED_OVERLAP_TOKENS)
        used = "co_dinh"

    for i, chunk in enumerate(chunks, start=1):
        chunk.thu_tu = i
    return chunks, used
