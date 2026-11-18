"""Cấu hình toàn hệ thống, đọc DUY NHẤT từ file .env ở thư mục gốc dự án.

Mọi service import `get_settings()` thay vì đọc os.environ trực tiếp, nhờ vậy
không có mật khẩu/khoá/URL nào bị hard-code trong code.
"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# backend/src/shared/config.py -> parents[3] = thư mục gốc dự án (tro-ly-hoc-vu/)
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
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
    cors_origins: str = "http://localhost:5173"

    demo_now: datetime | None = None
    ten_truong: str = "Trường Đại học"

    # ---------- LLM ----------
    llm_model: str = ""
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1500

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

    @field_validator("demo_now", mode="before")
    @classmethod
    def _empty_demo_now(cls, v: object) -> object:
        # "DEMO_NOW=" (bỏ trống) nghĩa là dùng giờ hệ thống
        if isinstance(v, str) and not v.strip():
            return None
        return v

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
