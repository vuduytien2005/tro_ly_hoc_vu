"""Client gọi API nội bộ của server `quy_che` (/internal/...) cho trang quản trị.

Chỉ tiến trình quy_che đọc/ghi ChromaDB (xem docstring src/mcp_servers/quy_che.py), nên
assistant_api không tự lập chỉ mục mà nhờ quy_che: lưu tệp + bản ghi `van_ban` -> gọi
POST /internal/documents/{id}/index -> quy_che lập chỉ mục nền, cập nhật `van_ban.trang_thai`.
Xác thực: `Authorization: Bearer <INTERNAL_API_TOKEN>` (như khi gọi /mcp).
"""

from typing import Any

import httpx

from src.assistant_api.errors import ApiError
from src.shared.config import get_settings

TIMEOUT_SECONDS = 120.0  # lần gọi đầu, quy_che có thể đang nạp mô hình embedding
UNAVAILABLE = ApiError(
    "QUY_CHE_KHONG_KET_NOI",
    "Không kết nối được server quy_che (cổng 9104). Kiểm tra service đã chạy chưa.",
    503,
)


class RagAdminClient:
    def __init__(
        self,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._transport = transport  # test: ASGITransport tới app quy_che trong tiến trình

    async def _request(
        self, method: str, path: str, json_body: dict[str, Any] | None = None
    ) -> httpx.Response:
        settings = get_settings()
        base_url = self._base_url or f"http://127.0.0.1:{settings.mcp_quy_che_port}"
        async with httpx.AsyncClient(
            base_url=base_url,
            transport=self._transport,
            headers={"Authorization": f"Bearer {settings.internal_api_token}"},
            timeout=TIMEOUT_SECONDS,
        ) as client:
            try:
                return await client.request(method, path, json=json_body)
            except httpx.HTTPError as exc:
                raise UNAVAILABLE from exc

    @staticmethod
    def _raise_for(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            body = response.json()
        except ValueError:
            body = {}
        raise ApiError(
            str(body.get("code") or f"QUY_CHE_LOI_{response.status_code}"),
            str(body.get("detail") or "Server quy_che báo lỗi."),
            response.status_code if response.status_code < 500 else 502,
        )

    async def index(self, van_ban_id: int) -> None:
        """Yêu cầu lập chỉ mục nền (trả về ngay, không chờ xong)."""
        self._raise_for(await self._request("POST", f"/internal/documents/{van_ban_id}/index"))

    async def delete(self, van_ban_id: int) -> bool:
        """Xóa văn bản + đoạn + vector. False nếu quy_che không thấy văn bản."""
        response = await self._request("DELETE", f"/internal/documents/{van_ban_id}")
        if response.status_code == 404:
            return False
        self._raise_for(response)
        return True

    async def search(self, body: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", "/internal/rag/search", body)
        self._raise_for(response)
        result: dict[str, Any] = response.json()
        return result
