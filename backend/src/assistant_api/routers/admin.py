"""API quản trị (/api/admin/*) — chỉ tài khoản vai_tro = admin (sinh viên -> 403).

- Tài liệu: lưu tệp vào UPLOAD_DIR + bản ghi `van_ban` (dang_xu_ly), rồi nhờ server quy_che lập chỉ
  mục nền (xem src/assistant_api/rag_admin.py). Giao diện hỏi lại danh sách để thấy trạng thái đổi.
- MCP & quyền: bật/tắt, cần xác nhận, mức rủi ro. Chính sách được đọc lại từ CSDL ở mỗi lượt chat
  -> đổi là có hiệu lực ngay ở câu hỏi tiếp theo.
- Nhật ký, thống kê: chỉ đọc.
"""

import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from src.assistant_api.deps import DbSession, require_admin
from src.assistant_api.errors import ApiError, conflict, not_found
from src.assistant_api.models import (
    CongCu,
    DanhGiaCauTraLoi,
    DoanVanBan,
    HoiThoai,
    LuotGoiCongCu,
    McpServer,
    NguoiDung,
    TinNhan,
    VanBan,
)
from src.assistant_api.rag_admin import RagAdminClient
from src.assistant_api.schemas_admin import (
    AuditLogDetail,
    AuditLogOut,
    AuditLogPage,
    AuditUser,
    ChienLuocChunk,
    ChunkOut,
    ChunkPage,
    DailyCount,
    DislikedAnswer,
    DocumentOut,
    LoaiVanBan,
    McpServerOut,
    RagSearchIn,
    StatsOut,
    ToolOut,
    ToolPatch,
    ToolUsage,
    TrangThaiLuotGoi,
)
from src.shared.config import get_settings
from src.shared.time import to_db, wall_clock

router = APIRouter(prefix="/api/admin", tags=["Quản trị"], dependencies=[Depends(require_admin)])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UNSAFE_CHARS = re.compile(r"[^\w.\- ]+")
CONFIRM_PREFIX, CANCEL_PREFIX = "Xác nhận: ", "Hủy: "  # tin hệ thống, không tính là câu hỏi
WRITE_RISKS = ("ghi", "nhay_cam")


def upload_dir() -> Path:
    return get_settings().upload_dir


def rag_admin(request: Request) -> RagAdminClient:
    client: RagAdminClient = request.app.state.rag_admin
    return client


# =============================================================================
# Tài liệu
# =============================================================================
def _get_document(db: Session, van_ban_id: int) -> VanBan:
    van_ban = db.get(VanBan, van_ban_id)
    if van_ban is None:
        raise not_found("VAN_BAN_KHONG_TON_TAI", "Không tìm thấy văn bản.")
    return van_ban


def _optional_int(value: str | None, field: str) -> int | None:
    if value is None or not value.strip():
        return None
    text = value.strip().upper().removeprefix("K")
    if not text.isdigit() or not 0 <= int(text) <= 99:
        raise ApiError(
            "DU_LIEU_KHONG_HOP_LE", f"{field} phải là số khóa 2 chữ số (vd 22 hoặc K22).", 422
        )
    return int(text)


def _optional_date(value: str | None) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ApiError(
            "DU_LIEU_KHONG_HOP_LE", "Ngày hiệu lực phải có dạng YYYY-MM-DD.", 422
        ) from exc


def safe_filename(name: str) -> str:
    """Chỉ giữ tên tệp (bỏ thư mục), thay ký tự lạ -> chặn ghi ra ngoài UPLOAD_DIR."""
    base = Path(name.replace("\\", "/")).name
    stem, ext = Path(base).stem, Path(base).suffix.lower()
    stem = UNSAFE_CHARS.sub("_", stem).strip(" ._") or "van_ban"
    return f"{stem[:120]}{ext}"


def _looks_valid(ext: str, head: bytes) -> bool:
    if ext == ".pdf":
        return head.startswith(b"%PDF")
    if ext == ".docx":
        return head.startswith(b"PK")  # DOCX là tệp zip
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as exc:  # có thể cắt giữa ký tự nhiều byte ở cuối
        return exc.start >= len(head) - 3
    return True


async def _save_upload(tep: UploadFile) -> tuple[str, Path]:
    original = safe_filename(tep.filename or "")
    ext = Path(original).suffix
    if ext not in ALLOWED_EXTENSIONS:
        raise ApiError("DINH_DANG_KHONG_HO_TRO", "Chỉ nhận tệp PDF, DOCX hoặc TXT.", 415)
    folder = upload_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex[:8]}_{original}"
    size = 0
    try:
        with path.open("wb") as out:
            while chunk := await tep.read(1024 * 1024):
                if size == 0 and not _looks_valid(ext, chunk[:4096]):
                    raise ApiError(
                        "TEP_KHONG_HOP_LE", f"Nội dung tệp không đúng định dạng {ext}.", 415
                    )
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise ApiError("TEP_QUA_LON", "Tệp vượt quá 20 MB.", 413)
                out.write(chunk)
        if size == 0:
            raise ApiError("TEP_RONG", "Tệp tải lên đang trống.", 422)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return original, path


def _remove_uploaded(path_text: str | None) -> None:
    """Xóa tệp gốc nếu nằm trong UPLOAD_DIR (không đụng tệp nạp bằng script ở nơi khác)."""
    if not path_text:
        return
    path = Path(path_text).resolve()
    if path.is_relative_to(upload_dir().resolve()):
        path.unlink(missing_ok=True)


async def _start_indexing(db: Session, client: RagAdminClient, van_ban: VanBan) -> None:
    try:
        await client.index(van_ban.id)
    except ApiError as exc:
        van_ban.trang_thai = "loi"
        van_ban.loi = exc.message
        db.commit()
        raise


@router.get("/documents", response_model=list[DocumentOut], summary="Danh sách văn bản")
def list_documents(db: DbSession) -> list[VanBan]:
    return list(db.scalars(select(VanBan).order_by(VanBan.updated_at.desc(), VanBan.id.desc())))


@router.post(
    "/documents",
    response_model=DocumentOut,
    status_code=202,
    summary="Tải lên văn bản -> lập chỉ mục nền (trùng tên + loại + phiên bản thì thay thế)",
)
async def upload_document(
    db: DbSession,
    client: Annotated[RagAdminClient, Depends(rag_admin)],
    tep: Annotated[UploadFile, File(description="PDF / DOCX / TXT, tối đa 20 MB")],
    ten: Annotated[str, Form(min_length=1, max_length=255)],
    loai: Annotated[LoaiVanBan, Form()],
    phien_ban: Annotated[str, Form(min_length=1, max_length=50)],
    ap_dung_tu_khoa: Annotated[str | None, Form()] = None,
    ap_dung_den_khoa: Annotated[str | None, Form()] = None,
    ngay_hieu_luc: Annotated[str | None, Form()] = None,
    chien_luoc_chunk: Annotated[ChienLuocChunk, Form()] = "theo_dieu",
) -> VanBan:
    ten, phien_ban = ten.strip(), phien_ban.strip()
    if not ten or not phien_ban:
        raise ApiError("DU_LIEU_KHONG_HOP_LE", "Cần nhập tên và phiên bản văn bản.", 422)
    tu = _optional_int(ap_dung_tu_khoa, "Áp dụng từ khóa")
    den = _optional_int(ap_dung_den_khoa, "Áp dụng đến khóa")
    if tu is not None and den is not None and tu > den:
        raise ApiError(
            "DU_LIEU_KHONG_HOP_LE",
            "Khóa bắt đầu áp dụng phải nhỏ hơn hoặc bằng khóa kết thúc.",
            422,
        )
    hieu_luc = _optional_date(ngay_hieu_luc)

    van_ban = db.scalar(
        select(VanBan).where(VanBan.ten == ten, VanBan.loai == loai, VanBan.phien_ban == phien_ban)
    )
    if van_ban is not None and van_ban.trang_thai == "dang_xu_ly":
        raise conflict("VAN_BAN_DANG_XU_LY", "Văn bản này đang được lập chỉ mục, thử lại sau.")

    ten_tep, path = await _save_upload(tep)
    old_path = van_ban.duong_dan_tep if van_ban is not None else None
    if van_ban is None:
        van_ban = VanBan(ten=ten, loai=loai, phien_ban=phien_ban)
        db.add(van_ban)
    van_ban.ten_tep = ten_tep
    van_ban.duong_dan_tep = str(path)
    van_ban.ap_dung_tu_khoa = tu
    van_ban.ap_dung_den_khoa = den
    van_ban.ngay_hieu_luc = hieu_luc
    van_ban.chien_luoc_chunk = chien_luoc_chunk
    van_ban.trang_thai = "dang_xu_ly"
    van_ban.loi = None
    db.commit()
    if old_path and old_path != str(path):
        _remove_uploaded(old_path)

    await _start_indexing(db, client, van_ban)
    db.refresh(van_ban)
    return van_ban


@router.get(
    "/documents/{van_ban_id}/chunks", response_model=ChunkPage, summary="Xem các đoạn đã chia"
)
def list_chunks(
    van_ban_id: int,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ChunkPage:
    _get_document(db, van_ban_id)
    total = db.scalar(select(func.count(DoanVanBan.id)).where(DoanVanBan.van_ban_id == van_ban_id))
    rows = db.scalars(
        select(DoanVanBan)
        .where(DoanVanBan.van_ban_id == van_ban_id)
        .order_by(DoanVanBan.thu_tu)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ChunkPage(
        tong=total or 0,
        trang_so=page,
        so_moi_trang=page_size,
        doan=[ChunkOut.model_validate(r) for r in rows],
    )


@router.post(
    "/documents/{van_ban_id}/reindex",
    response_model=DocumentOut,
    status_code=202,
    summary="Lập chỉ mục lại từ tệp gốc",
)
async def reindex_document(
    van_ban_id: int, db: DbSession, client: Annotated[RagAdminClient, Depends(rag_admin)]
) -> VanBan:
    van_ban = _get_document(db, van_ban_id)
    if van_ban.trang_thai == "dang_xu_ly":
        raise conflict("VAN_BAN_DANG_XU_LY", "Văn bản này đang được lập chỉ mục, thử lại sau.")
    if not Path(van_ban.duong_dan_tep).is_file():
        raise conflict(
            "TEP_GOC_KHONG_CON", "Không còn tệp gốc trên máy chủ, hãy tải văn bản lên lại."
        )
    van_ban.trang_thai = "dang_xu_ly"
    van_ban.loi = None
    db.commit()
    await _start_indexing(db, client, van_ban)
    db.refresh(van_ban)
    return van_ban


@router.delete("/documents/{van_ban_id}", status_code=204, summary="Xóa văn bản + vector")
async def delete_document(
    van_ban_id: int, db: DbSession, client: Annotated[RagAdminClient, Depends(rag_admin)]
) -> None:
    van_ban = _get_document(db, van_ban_id)
    if van_ban.trang_thai == "dang_xu_ly":
        raise conflict("VAN_BAN_DANG_XU_LY", "Văn bản đang được lập chỉ mục, chưa xóa được.")
    path = van_ban.duong_dan_tep
    db.rollback()  # quy_che xóa bản ghi trong phiên của nó; tránh giữ khóa đọc ở phiên này
    if not await client.delete(van_ban_id):
        raise not_found("VAN_BAN_KHONG_TON_TAI", "Không tìm thấy văn bản.")
    _remove_uploaded(path)


@router.post("/rag/search", summary="Thử truy xuất (debug): bật/tắt từng thành phần, kèm điểm")
async def rag_search(
    body: RagSearchIn, client: Annotated[RagAdminClient, Depends(rag_admin)]
) -> dict[str, Any]:
    return await client.search(body.model_dump())


# =============================================================================
# MCP & quyền
# =============================================================================
def _servers_out(request: Request, db: Session) -> list[McpServerOut]:
    registry = request.app.state.registry
    available = registry.available_tool_names()
    servers = db.scalars(select(McpServer).order_by(McpServer.id)).all()
    return [
        McpServerOut(
            id=s.id,
            ten=s.ten,
            mo_ta=s.mo_ta,
            dia_chi=s.dia_chi,
            bat=bool(s.bat),
            trang_thai=registry.server_status.get(s.ten, "chưa đồng bộ"),
            cong_cu=[
                ToolOut(
                    id=t.id,
                    ten=t.ten,
                    mo_ta=t.mo_ta,
                    muc_rui_ro=t.muc_rui_ro,
                    can_xac_nhan=bool(t.can_xac_nhan),
                    bat=bool(t.bat),
                    co_tren_server=t.ten in available,
                )
                for t in sorted(s.cong_cu, key=lambda t: t.ten)
            ],
        )
        for s in servers
    ]


@router.get(
    "/mcp-servers", response_model=list[McpServerOut], summary="Server, trạng thái và công cụ"
)
def list_mcp_servers(request: Request, db: DbSession) -> list[McpServerOut]:
    return _servers_out(request, db)


@router.post(
    "/mcp-servers/refresh",
    response_model=list[McpServerOut],
    summary="Kết nối lại các server, đồng bộ danh mục công cụ",
)
async def refresh_mcp_servers(request: Request, db: DbSession) -> list[McpServerOut]:
    await request.app.state.registry.sync(db)
    return _servers_out(request, db)


@router.patch("/tools/{tool_id}", response_model=ToolOut, summary="Đổi chính sách một công cụ")
def update_tool(request: Request, tool_id: int, body: ToolPatch, db: DbSession) -> ToolOut:
    tool = db.get(CongCu, tool_id)
    if tool is None:
        raise not_found("CONG_CU_KHONG_TON_TAI", "Không tìm thấy công cụ.")
    if body.muc_rui_ro is not None:
        tool.muc_rui_ro = body.muc_rui_ro
    if body.can_xac_nhan is not None:
        tool.can_xac_nhan = body.can_xac_nhan
    if body.bat is not None:
        tool.bat = body.bat
    # Quy tắc bảo mật 2: công cụ thay đổi dữ liệu luôn phải chờ sinh viên xác nhận
    if tool.muc_rui_ro in WRITE_RISKS and not tool.can_xac_nhan:
        db.rollback()
        raise ApiError(
            "KHONG_THE_BO_XAC_NHAN",
            "Công cụ mức rủi ro 'ghi' hoặc 'nhạy cảm' bắt buộc phải cần xác nhận.",
            422,
        )
    db.commit()
    return ToolOut(
        id=tool.id,
        ten=tool.ten,
        mo_ta=tool.mo_ta,
        muc_rui_ro=tool.muc_rui_ro,
        can_xac_nhan=bool(tool.can_xac_nhan),
        bat=bool(tool.bat),
        co_tren_server=tool.ten in request.app.state.registry.available_tool_names(),
    )


# =============================================================================
# Nhật ký
# =============================================================================
def _injected(log: LuotGoiCongCu) -> bool:
    return log.tham_so_llm is not None and log.tham_so_llm != log.tham_so


def _log_out(log: LuotGoiCongCu, user: NguoiDung) -> dict[str, Any]:
    return {
        "id": log.id,
        "created_at": log.created_at,
        "nguoi_dung": AuditUser(id=user.id, ho_ten=user.ho_ten, email=user.email),
        "hoi_thoai_id": log.hoi_thoai_id,
        "mcp_server": log.mcp_server,
        "ten_cong_cu": log.ten_cong_cu,
        "trang_thai": log.trang_thai,
        "ly_do": log.ly_do,
        "thoi_gian_ms": log.thoi_gian_ms,
        "tham_so": log.tham_so,
        "tham_so_llm": log.tham_so_llm,
        "da_tiem_ngu_canh": _injected(log),
    }


def _day_range(tu: date | None, den: date | None) -> tuple[datetime | None, datetime | None]:
    """[tu 00:00, den+1 00:00) theo giờ Việt Nam (CSDL lưu giờ VN không kèm múi giờ)."""
    start = datetime.combine(tu, datetime.min.time()) if tu else None
    end = datetime.combine(den + timedelta(days=1), datetime.min.time()) if den else None
    return start, end


@router.get("/audit-logs", response_model=AuditLogPage, summary="Nhật ký gọi công cụ")
def list_audit_logs(
    db: DbSession,
    tu: date | None = None,
    den: date | None = None,
    nguoi_dung_id: int | None = None,
    ten_cong_cu: Annotated[str | None, Query(max_length=100)] = None,
    trang_thai: TrangThaiLuotGoi | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AuditLogPage:
    start, end = _day_range(tu, den)
    conditions = []
    if start is not None:
        conditions.append(LuotGoiCongCu.created_at >= start)
    if end is not None:
        conditions.append(LuotGoiCongCu.created_at < end)
    if nguoi_dung_id is not None:
        conditions.append(LuotGoiCongCu.nguoi_dung_id == nguoi_dung_id)
    if ten_cong_cu:
        conditions.append(LuotGoiCongCu.ten_cong_cu == ten_cong_cu)
    if trang_thai:
        conditions.append(LuotGoiCongCu.trang_thai == trang_thai)

    total = db.scalar(select(func.count(LuotGoiCongCu.id)).where(*conditions))
    rows = db.execute(
        select(LuotGoiCongCu, NguoiDung)
        .join(NguoiDung, NguoiDung.id == LuotGoiCongCu.nguoi_dung_id)
        .where(*conditions)
        .order_by(LuotGoiCongCu.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AuditLogPage(
        tong=total or 0,
        trang_so=page,
        so_moi_trang=page_size,
        luot_goi=[AuditLogOut.model_validate(_log_out(log, user)) for log, user in rows],
    )


@router.get("/audit-logs/{log_id}", response_model=AuditLogDetail, summary="Chi tiết một lượt gọi")
def get_audit_log(log_id: int, db: DbSession) -> AuditLogDetail:
    row = db.execute(
        select(LuotGoiCongCu, NguoiDung)
        .join(NguoiDung, NguoiDung.id == LuotGoiCongCu.nguoi_dung_id)
        .where(LuotGoiCongCu.id == log_id)
    ).first()
    if row is None:
        raise not_found("NHAT_KY_KHONG_TON_TAI", "Không tìm thấy lượt gọi.")
    log, user = row
    return AuditLogDetail.model_validate({**_log_out(log, user), "ket_qua": log.ket_qua})


# =============================================================================
# Thống kê
# =============================================================================
@router.get("/stats", response_model=StatsOut, summary="Thống kê sử dụng (mặc định 30 ngày)")
def stats(db: DbSession, tu: date | None = None, den: date | None = None) -> StatsOut:
    today = to_db(wall_clock()).date()
    den = den or today
    tu = tu or den - timedelta(days=29)
    if tu > den:
        raise ApiError("DU_LIEU_KHONG_HOP_LE", "Ngày bắt đầu phải trước ngày kết thúc.", 422)
    start, end = _day_range(tu, den)

    in_range_msg = (TinNhan.created_at >= start, TinNhan.created_at < end)
    is_question = (
        TinNhan.vai_tro == "user",
        TinNhan.noi_dung.not_like(f"{CONFIRM_PREFIX}%"),
        TinNhan.noi_dung.not_like(f"{CANCEL_PREFIX}%"),
    )

    so_hoi_thoai = db.scalar(
        select(func.count(HoiThoai.id)).where(
            HoiThoai.created_at >= start, HoiThoai.created_at < end
        )
    )
    so_cau_hoi = db.scalar(select(func.count(TinNhan.id)).where(*in_range_msg, *is_question))
    so_danh_gia, so_huu_ich = _ratings(db, start, end)
    avg_ms = db.scalar(
        select(func.avg(TinNhan.thoi_gian_ms)).where(
            *in_range_msg, TinNhan.vai_tro == "assistant", TinNhan.thoi_gian_ms.is_not(None)
        )
    )

    in_range_log = (LuotGoiCongCu.created_at >= start, LuotGoiCongCu.created_at < end)
    so_luot_goi = db.scalar(select(func.count(LuotGoiCongCu.id)).where(*in_range_log))
    failed = func.sum(func.iif(LuotGoiCongCu.trang_thai.in_(("loi", "bi_tu_choi")), 1, 0))
    top_tools = db.execute(
        select(LuotGoiCongCu.ten_cong_cu, func.count(LuotGoiCongCu.id).label("n"), failed)
        .where(*in_range_log)
        .group_by(LuotGoiCongCu.ten_cong_cu)
        .order_by(func.count(LuotGoiCongCu.id).desc(), LuotGoiCongCu.ten_cong_cu)
        .limit(10)
    ).all()

    day = cast(TinNhan.created_at, Date)
    per_day = dict(
        db.execute(
            select(day, func.count(TinNhan.id)).where(*in_range_msg, *is_question).group_by(day)
        ).all()
    )
    theo_ngay = [
        DailyCount(ngay=tu + timedelta(days=i), so_cau_hoi=per_day.get(tu + timedelta(days=i), 0))
        for i in range((den - tu).days + 1)
    ]

    return StatsOut(
        tu=tu,
        den=den,
        so_hoi_thoai=so_hoi_thoai or 0,
        so_cau_hoi=so_cau_hoi or 0,
        so_danh_gia=so_danh_gia,
        so_huu_ich=so_huu_ich,
        ti_le_huu_ich=round(so_huu_ich / so_danh_gia, 4) if so_danh_gia else None,
        thoi_gian_phan_hoi_tb_ms=int(avg_ms) if avg_ms is not None else None,
        so_luot_goi_cong_cu=so_luot_goi or 0,
        top_cong_cu=[ToolUsage(ten_cong_cu=n, so_lan=c, so_loi=f or 0) for n, c, f in top_tools],
        theo_ngay=theo_ngay,
        cau_bi_che=_disliked(db, start, end),
    )


def _ratings(db: Session, start: datetime | None, end: datetime | None) -> tuple[int, int]:
    total, liked = db.execute(
        select(
            func.count(DanhGiaCauTraLoi.id),
            func.sum(func.iif(DanhGiaCauTraLoi.diem == 1, 1, 0)),
        ).where(DanhGiaCauTraLoi.created_at >= start, DanhGiaCauTraLoi.created_at < end)
    ).one()
    return total or 0, liked or 0


def _disliked(
    db: Session, start: datetime | None, end: datetime | None, limit: int = 20
) -> list[DislikedAnswer]:
    question = TinNhan.__table__.alias("cau_hoi")
    previous_question = (
        select(question.c.noi_dung)
        .where(
            question.c.hoi_thoai_id == TinNhan.hoi_thoai_id,
            question.c.vai_tro == "user",
            question.c.id < TinNhan.id,
        )
        .order_by(question.c.id.desc())
        .limit(1)
        .correlate(TinNhan)
        .scalar_subquery()
    )
    rows = db.execute(
        select(DanhGiaCauTraLoi, TinNhan, NguoiDung.email, previous_question)
        .join(TinNhan, TinNhan.id == DanhGiaCauTraLoi.tin_nhan_id)
        .join(NguoiDung, NguoiDung.id == DanhGiaCauTraLoi.nguoi_dung_id)
        .where(
            DanhGiaCauTraLoi.diem == -1,
            DanhGiaCauTraLoi.created_at >= start,
            DanhGiaCauTraLoi.created_at < end,
        )
        .order_by(DanhGiaCauTraLoi.created_at.desc(), DanhGiaCauTraLoi.id.desc())
        .limit(limit)
    ).all()
    return [
        DislikedAnswer(
            tin_nhan_id=message.id,
            hoi_thoai_id=message.hoi_thoai_id,
            nguoi_dung=email,
            cau_hoi=q,
            cau_tra_loi=message.noi_dung[:1000],
            gop_y=rating.gop_y,
            created_at=rating.created_at,
        )
        for rating, message, email, q in rows
    ]
