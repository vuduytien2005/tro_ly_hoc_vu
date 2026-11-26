"""Client gọi thẳng qlsv_api cho trang quản trị (AD-09 cấp tài khoản, AD-10 hồ sơ sinh viên).

Ngoại lệ duy nhất assistant_api gọi thẳng QLSV (docs/02 mục 1). Không đi qua MCP vì đây là thao
tác của quản trị viên / phòng đào tạo, không phải hành động của Agent. Không đọc/ghi thẳng CSDL
`tlhv_qlsv`: mọi ràng buộc nghiệp vụ (mã SV, email trùng, ngành/khóa hợp lệ) do qlsv_api kiểm tra.
Xác thực: header X-Internal-Token (như MCP server gọi qlsv_api).
"""

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from src.assistant_api.errors import ApiError
from src.shared.config import get_settings
from src.shared.security import INTERNAL_TOKEN_HEADER

TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class StudentIdentity:
    """Phần hồ sơ được sao vào tài khoản trợ lý (nguoi_dung)."""

    ma_sv: str
    ho_ten: str
    email: str
    ma_khoa: str

    @classmethod
    def from_profile(cls, data: dict[str, Any]) -> "StudentIdentity":
        return cls(
            ma_sv=str(data["ma_sv"]),
            ho_ten=str(data["ho_ten"]),
            email=str(data["email"]),
            ma_khoa=str(data["khoa"]),  # qlsv trả mã khóa học (K22...) ở trường `khoa`
        )


class QlsvDirectory:
    def __init__(
        self,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._transport = transport  # test: ASGITransport tới app qlsv trong tiến trình

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        settings = get_settings()
        clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        async with httpx.AsyncClient(
            base_url=self._base_url or settings.qlsv_api_url,
            transport=self._transport,
            headers={INTERNAL_TOKEN_HEADER: settings.internal_api_token},
            timeout=TIMEOUT_SECONDS,
        ) as client:
            try:
                response = await client.request(method, path, params=clean, json=json_body)
            except httpx.HTTPError as exc:
                raise ApiError(
                    "QLSV_KHONG_KET_NOI",
                    "Không kết nối được hệ thống quản lý sinh viên (cổng 8001).",
                    503,
                ) from exc
        if response.is_success:
            return response.json()
        try:
            body = response.json()
        except ValueError:
            body = {}
        # Lỗi nghiệp vụ 4xx của qlsv (mã SV trùng, ngành không có...) chuyển nguyên văn
        raise ApiError(
            str(body.get("code") or f"QLSV_LOI_{response.status_code}"),
            str(body.get("detail") or "Hệ thống quản lý sinh viên báo lỗi, thử lại sau."),
            response.status_code if response.status_code < 500 else 502,
        )

    @staticmethod
    def _student_path(ma_sv: str) -> str:
        return f"/internal/students/{quote(ma_sv.strip(), safe='')}"

    async def get_profile(self, ma_sv: str) -> dict[str, Any]:
        try:
            result: dict[str, Any] = await self._request("GET", self._student_path(ma_sv))
        except ApiError as exc:
            if exc.status == 404:
                raise ApiError(
                    "SV_KHONG_TON_TAI",
                    f"Không tìm thấy sinh viên {ma_sv} trong hệ thống QLSV.",
                    404,
                ) from exc
            raise
        return result

    async def get_student(self, ma_sv: str) -> StudentIdentity:
        return StudentIdentity.from_profile(await self.get_profile(ma_sv))

    async def list_students(self, params: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", "/internal/students", params=params)
        return result

    async def list_attention(self) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", "/internal/students/attention")
        return result

    async def list_programs(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._request("GET", "/internal/programs")
        return result

    async def create_student(self, body: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("POST", "/internal/students", json_body=body)
        return result

    async def update_student(self, ma_sv: str, body: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = await self._request(
            "PATCH", self._student_path(ma_sv), json_body=body
        )
        return result

    async def list_requests(self, params: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", "/internal/requests", params=params)
        return result

    async def update_request(self, ma_don: str, body: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = await self._request(
            "PATCH", f"/internal/requests/{quote(ma_don.strip(), safe='')}", json_body=body
        )
        return result
