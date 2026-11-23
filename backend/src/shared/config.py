"""Cấu hình toàn hệ thống, đọc DUY NHẤT từ file .env ở thư mục gốc dự án.

Mọi service import `get_settings()` thay vì đọc os.environ trực tiếp, nhờ vậy
không có mật khẩu/khoá/URL nào bị hard-code trong code.
"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# backend/src/shared/config.py -> parents[3] = thư mục gốc dự án (tro-ly-hoc-vu/)
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
MIN_SECRET_LENGTH = 32  # JWT_SECRET, INTERNAL_API_TOKEN
ENV_FILE: Path = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- SQL Server ----------
    db_server: str = r"localhost\SQLEXPRESS01"  # "<máy>\<instance>" hoặc "<máy>,<cổng>"
    db_driver: str = "ODBC Driver 18 for SQL Server"
    # Bỏ trống DB_USER -> Windows Authentication (Trusted_Connection)
    db_user: str = ""
    db_password: str = ""
    # Driver 18 bật mã hóa mặc định; SQL Server cục bộ dùng chứng chỉ tự ký
    db_trust_server_certificate: bool = True
    db_qlsv: str = "tlhv_qlsv"
    db_assistant: str = "tlhv_assistant"

    # ---------- Bảo mật ----------
    jwt_secret: str
    jwt_expire_minutes: int = 480
    internal_api_token: str

    # ---------- Dịch vụ ----------
    qlsv_api_url: str = "http://127.0.0.1:8001"
    qlsv_api_port: int = 8001
    assistant_api_port: int = 8000
    mcp_dao_tao_port: int = 9101
    mcp_ctsv_port: int = 9102
    mcp_tai_chinh_port: int = 9103
    mcp_quy_che_port: int = 9104
    mcp_thu_vien_port: int = 9105  # server bổ sung: quản trị viên thêm trên giao diện
    cors_origins: str = "http://localhost:5173"

    demo_now: datetime | None = None
    # Chế độ trình bày (demo trước hội đồng): bật API trace + bảng "Bên trong Agent" trên web.
    # Mặc định tắt: triển khai thật không lộ tên công cụ / tham số nội bộ cho sinh viên.
    che_do_trinh_bay: bool = False
    ten_truong: str = "Trường Đại học"

    # ---------- LLM ----------
    llm_model: str = ""
    # Bỏ trống = không gửi temperature (Claude Opus 5.5/Sonnet 5.5... từ chối tham số này)
    llm_temperature: float | None = None
    # Với Claude, token "thinking" tính vào max_tokens -> để rộng
    llm_max_tokens: int = 16000
    # Mô hình thử lại khi mô hình chính từ chối trả lời (stop_reason "refusal"); trống = không
    llm_fallback_model: str = ""
    llm_timeout_seconds: float = 120.0
    # Cửa sổ ngữ cảnh khi chạy mô hình cục bộ qua Ollama (ollama/..., ollama_chat/...).
    # Trống = OLLAMA_DEFAULT_NUM_CTX. Mặc định của chính Ollama (2–4 nghìn token) LẶNG LẼ cắt
    # mất danh sách công cụ.
    llm_num_ctx: int | None = None
    # Số lần LiteLLM tự thử lại (có giãn cách) khi lỗi 429 / quá tải — cần cho gói miễn phí
    # (vd Gemini giới hạn số lượt mỗi phút)
    llm_num_retries: int = 2
    # Gặp 429/503 thì chờ đúng thời gian nhà cung cấp yêu cầu rồi gọi lại, tổng tối đa bấy
    # nhiêu giây cho một lượt (0 = báo lỗi ngay). Gemini miễn phí (5 lượt/phút): đặt 90.
    llm_rate_limit_wait_seconds: float = 0.0

    # ---------- RAG ----------
    embedding_model: str = "intfloat/multilingual-e5-base"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_enabled: bool = False
    chroma_dir: Path = Path("./data/chroma")
    upload_dir: Path = Path("./data/van_ban")
    chunk_max_tokens: int = 512
    retrieve_top_k: int = 5

    # ---------- Agent ----------
    agent_max_steps: int = 6
    agent_history_messages: int = 20
    action_expire_minutes: int = 10

    @field_validator("demo_now", "llm_temperature", "llm_num_ctx", mode="before")
    @classmethod
    def _empty_demo_now(cls, v: object) -> object:
        # "DEMO_NOW=" (bỏ trống) nghĩa là dùng giờ hệ thống
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("jwt_secret", "internal_api_token", mode="after")
    @classmethod
    def _strong_secret(cls, v: str, info: ValidationInfo) -> str:
        # Quy tắc bảo mật 4: chuỗi mẫu của .env.example công khai trên Git -> ai cũng ký được JWT
        # admin / gọi được MCP server. Từ chối khởi động thay vì chạy với bí mật yếu.
        name = (info.field_name or "").upper()
        weak = len(v.strip()) < MIN_SECRET_LENGTH or len(set(v.strip())) < 10  # vd "AAAA…"
        if v.strip().lower().startswith("thay_bang") or weak:
            raise ValueError(
                f"{name} trong .env phải là chuỗi ngẫu nhiên dài ít nhất {MIN_SECRET_LENGTH} ký tự "
                "(không dùng giá trị mẫu). Tạo bằng: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return v.strip()

    @field_validator("chroma_dir", "upload_dir", mode="after")
    @classmethod
    def _resolve_from_root(cls, v: Path) -> Path:
        # Đường dẫn tương đối tính từ thư mục gốc dự án, không phụ thuộc thư mục đang đứng
        return v if v.is_absolute() else (PROJECT_ROOT / v).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def _mssql_url(self, database: str) -> URL:
        query: dict[str, str] = {"driver": self.db_driver}
        if self.db_trust_server_certificate:
            query["TrustServerCertificate"] = "yes"
        if not self.db_user:
            query["Trusted_Connection"] = "yes"  # đăng nhập bằng tài khoản Windows
        return URL.create(
            "mssql+pyodbc",
            username=self.db_user or None,
            password=self.db_password or None,
            host=self.db_server,
            database=database,
            query=query,
        )

    @property
    def qlsv_db_url(self) -> URL:
        return self._mssql_url(self.db_qlsv)

    @property
    def assistant_db_url(self) -> URL:
        return self._mssql_url(self.db_assistant)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # giá trị bắt buộc đến từ .env
