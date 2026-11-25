"""Kho hỏi đáp cán bộ (/api/admin/knowledge) — nâng cấp 10.

Mỗi mục là một cặp hỏi–đáp đã biên tập (bỏ thông tin cá nhân). Kho là MỘT văn bản loại `hoi_dap`
(không có tệp); mỗi lần thêm/sửa/gỡ, assistant_api nhờ quy_che lập chỉ mục lại văn bản đó (quy_che
dựng đoạn từ bảng kho_hoi_dap). Kho rỗng -> xóa văn bản. quy_che không chạy -> mục vẫn được lưu,
văn bản kho ở trạng thái `loi` (hiện trên trang), lập chỉ mục lại sau ở trang Tài liệu.
Thiết kế: docs/superpowers/specs/2026-11-25-kho-hoi-dap-va-lo-hong-tri-thuc-design.md.
"""

import contextlib
from datetime import timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.assistant_api.deps import CurrentUser, DbSession, require_admin
from src.assistant_api.errors import ApiError, not_found
from src.assistant_api.knowledge import (
    GAP_SOURCES,
    bad_rating_gaps,
    mark_in_knowledge_base,
    not_found_gaps,
    personal_info_problem,
    staff_question_gaps,
    unsupported_claim_gaps,
)
from src.assistant_api.models import KhoHoiDap, TinNhan, VanBan
from src.assistant_api.qlsv_directory import QlsvDirectory
from src.assistant_api.rag_admin import RagAdminClient
from src.assistant_api.routers.admin import _start_indexing, rag_admin
from src.assistant_api.routers.admin_users import qlsv_directory
from src.assistant_api.schemas_admin import KnowledgeIn, KnowledgeList, KnowledgeOut
from src.rag.knowledge import KNOWLEDGE_DOC, KNOWLEDGE_KIND, KNOWLEDGE_VERSION
from src.shared.time import now, to_db

router = APIRouter(
    prefix="/api/admin/knowledge",
    tags=["Quản trị — kho hỏi đáp"],
    dependencies=[Depends(require_admin)],
)

RagAdmin = Annotated[RagAdminClient, Depends(rag_admin)]
Directory = Annotated[QlsvDirectory, Depends(qlsv_directory)]


def knowledge_doc(db: Session) -> VanBan | None:
    return db.scalar(select(VanBan).where(VanBan.loai == KNOWLEDGE_KIND))


def _check(body: KnowledgeIn, db: Session) -> None:
    for field, text in (("Câu hỏi", body.cau_hoi), ("Câu trả lời", body.tra_loi)):
        problem = personal_info_problem(text)
        if problem:
            raise ApiError(
                "CO_THONG_TIN_CA_NHAN",
                f"{field} có {problem} — kho hỏi đáp trả cho mọi sinh viên, hãy bỏ thông tin "
                "cá nhân trước khi lưu.",
                422,
            )
    if body.tin_nhan_id is not None and db.get(TinNhan, body.tin_nhan_id) is None:
        raise not_found("TIN_NHAN_KHONG_TON_TAI", "Không tìm thấy tin nhắn nguồn.")


async def _sync_index(db: Session, client: RagAdminClient) -> None:
    """Đồng bộ văn bản kho với bảng: còn mục -> lập chỉ mục lại; hết mục -> xóa văn bản."""
    doc = knowledge_doc(db)
    count = db.scalar(select(func.count()).select_from(KhoHoiDap)) or 0
    if count == 0:
        if doc is not None:
            doc_id = doc.id
            db.rollback()  # quy_che xóa trong phiên của nó; không giữ khóa đọc ở phiên này
            await client.delete(doc_id)
        return
    if doc is None:
        doc = VanBan(
            ten=KNOWLEDGE_DOC,
            loai=KNOWLEDGE_KIND,
            phien_ban=KNOWLEDGE_VERSION,
            ten_tep="",
            duong_dan_tep="",
        )
        db.add(doc)
    doc.trang_thai = "dang_xu_ly"
    doc.loi = None
    db.commit()
    # quy_che không chạy: mục đã lưu; văn bản kho ghi `loi` để quản trị thấy và lập chỉ mục lại
    with contextlib.suppress(ApiError):
        await _start_indexing(db, client, doc)


@router.get("/gaps", summary="Lỗ hổng tri thức: thiếu căn cứ, không tìm thấy, hỏi cán bộ, 👎")
async def list_gaps(
    db: DbSession,
    directory: Directory,
    ngay: Annotated[int, Query(ge=1, le=365)] = 30,
    nguon: Literal["khong_can_cu", "khong_tim_thay", "hoi_can_bo", "danh_gia_xau"] | None = None,
) -> dict[str, Any]:
    until = now()
    since = until - timedelta(days=ngay)
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    if nguon in (None, "khong_can_cu"):
        items += unsupported_claim_gaps(db, since)
    if nguon in (None, "khong_tim_thay"):
        items += not_found_gaps(db, since)
    if nguon in (None, "danh_gia_xau"):
        items += bad_rating_gaps(db, since)
    if nguon in (None, "hoi_can_bo"):
        try:
            page = await directory.list_requests(
                {"loai_don": "hoi_dap", "page": 1, "page_size": 100}  # tối đa của qlsv
            )
            items += staff_question_gaps(page.get("don") or [], since)
        except ApiError:
            errors.append("hoi_can_bo")  # qlsv không chạy: vẫn trả hai nguồn còn lại
    mark_in_knowledge_base(db, items)
    items.sort(key=lambda m: m["thoi_gian"], reverse=True)
    counts = {source: sum(1 for m in items if m["nguon"] == source) for source in GAP_SOURCES}
    for m in items:
        m["thoi_gian"] = m["thoi_gian"].isoformat()
    return {
        "tu": since.isoformat(),
        "den": until.isoformat(),
        "dem": counts,
        "muc": items,
        "nguon_loi": errors,
    }


@router.get("", response_model=KnowledgeList, summary="Các mục trong kho + trạng thái lập chỉ mục")
def list_entries(db: DbSession) -> dict[str, Any]:
    # Đọc hết trước truy vấn thứ hai (pyodbc: một kết nối chỉ một con trỏ đang mở)
    entries = list(
        db.scalars(select(KhoHoiDap).order_by(KhoHoiDap.updated_at.desc(), KhoHoiDap.id))
    )
    return {"van_ban": knowledge_doc(db), "muc": entries}


@router.post("", response_model=KnowledgeOut, status_code=201, summary="Thêm mục vào kho")
async def add_entry(
    body: KnowledgeIn, db: DbSession, user: CurrentUser, client: RagAdmin
) -> KhoHoiDap:
    _check(body, db)
    stamp = to_db(now())
    entry = KhoHoiDap(**body.model_dump(), nguoi_tao_id=user.id, created_at=stamp, updated_at=stamp)
    db.add(entry)
    db.commit()
    entry_id = entry.id
    await _sync_index(db, client)
    return db.get_one(KhoHoiDap, entry_id)


@router.put("/{entry_id}", response_model=KnowledgeOut, summary="Sửa một mục")
async def edit_entry(
    entry_id: int, body: KnowledgeIn, db: DbSession, client: RagAdmin
) -> KhoHoiDap:
    entry = db.get(KhoHoiDap, entry_id)
    if entry is None:
        raise not_found("MUC_KHO_KHONG_TON_TAI", "Không tìm thấy mục trong kho hỏi đáp.")
    _check(body, db)
    for key, value in body.model_dump().items():
        setattr(entry, key, value)
    entry.updated_at = to_db(now())
    db.commit()
    await _sync_index(db, client)
    return db.get_one(KhoHoiDap, entry_id)


@router.delete("/{entry_id}", status_code=204, summary="Gỡ một mục khỏi kho")
async def delete_entry(entry_id: int, db: DbSession, client: RagAdmin) -> None:
    entry = db.get(KhoHoiDap, entry_id)
    if entry is None:
        raise not_found("MUC_KHO_KHONG_TON_TAI", "Không tìm thấy mục trong kho hỏi đáp.")
    db.delete(entry)
    db.commit()
    await _sync_index(db, client)
