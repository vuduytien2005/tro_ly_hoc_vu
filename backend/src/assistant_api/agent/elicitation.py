"""MCP elicitation trong luồng thẻ xác nhận (bổ sung 23/11/2026).

Sau khi sinh viên bấm "Xác nhận", MCP server có thể trả `InputRequiredResult` (MCP 2026-07-28):
cần người dùng điền thêm biểu mẫu (vd số điện thoại liên hệ khi bảo lưu) trước khi thực hiện.
Module này: đọc yêu cầu của server, chỉ nhận MỘT yêu cầu `elicitation/create` dạng form; kiểm dữ
liệu sinh viên điền theo `requestedSchema`; dựng `input_responses` để gọi lại công cụ.

Dữ liệu bổ sung đi thẳng web -> assistant_api -> MCP server, KHÔNG vào prompt LLM, không lưu vào
lịch sử hội thoại; nhật ký chỉ ghi TÊN trường.
Thiết kế: docs/superpowers/specs/2026-11-23-mcp-elicitation-resources-design.md
"""

from typing import Any

from jsonschema import Draft202012Validator

MAX_ROUNDS = 3  # số lần server được hỏi thêm cho một thẻ


class UnsupportedInputRequest(Exception):
    """Server yêu cầu thứ assistant_api không hỗ trợ (sampling, roots, URL, nhiều biểu mẫu...)."""


def form_request(input_required: dict[str, Any], rounds: int = 0) -> dict[str, Any]:
    """`InputRequiredResult` (đã chuyển JSON) -> bản ghi lưu ở `yeu_cau_bo_sung`."""
    requests = input_required.get("input_requests") or {}
    if len(requests) != 1:
        raise UnsupportedInputRequest(f"cần đúng 1 yêu cầu, nhận {len(requests)}")
    key, request = next(iter(requests.items()))
    params = request.get("params") or {}
    if request.get("method") != "elicitation/create" or params.get("mode", "form") != "form":
        raise UnsupportedInputRequest(f"không hỗ trợ {request.get('method')}/{params.get('mode')}")
    schema = params.get("requestedSchema")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise UnsupportedInputRequest("requestedSchema không hợp lệ")
    if rounds >= MAX_ROUNDS:
        raise UnsupportedInputRequest(f"server hỏi thêm quá {MAX_ROUNDS} lần")
    return {
        "khoa": key,
        "thong_diep": str(params.get("message") or "Cần thêm thông tin để thực hiện."),
        "schema": schema,
        "request_state": input_required.get("request_state"),
        "vong": rounds + 1,
    }


def public_form(stored: dict[str, Any] | None) -> dict[str, Any] | None:
    """Phần gửi cho trình duyệt: thông điệp + schema (không gửi khóa / request_state)."""
    if not stored:
        return None
    return {"thong_diep": stored["thong_diep"], "schema": stored["schema"]}


def _label(schema: dict[str, Any], field: str) -> str:
    prop = (schema.get("properties") or {}).get(field) or {}
    return str(prop.get("title") or field)


def form_errors(schema: dict[str, Any], data: dict[str, Any]) -> list[str]:
    """Lỗi theo từng trường (tiếng Việt, theo nhãn của server). Rỗng = hợp lệ.

    Chỉ nhận đúng các trường server khai báo (không cho gửi kèm trường lạ)."""
    strict = {**schema, "additionalProperties": False}
    messages: list[str] = []
    for e in sorted(Draft202012Validator(strict).iter_errors(data), key=lambda e: list(e.path)):
        if e.validator == "required":
            missing = str(e.message).split("'")[1] if "'" in str(e.message) else "?"
            messages.append(f"{_label(schema, missing)}: bắt buộc")
        elif e.validator == "additionalProperties":
            messages.append("Có trường không thuộc biểu mẫu")
        else:
            field = str(e.path[0]) if e.path else "?"
            messages.append(f"{_label(schema, field)}: không hợp lệ")
    return messages


def input_responses(stored: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Tham số gọi lại công cụ: câu trả lời 'accept' cho đúng khóa server đã cấp."""
    return {
        "input_responses": {stored["khoa"]: {"action": "accept", "content": data}},
        "request_state": stored.get("request_state"),
    }
