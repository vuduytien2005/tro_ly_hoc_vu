"""LLM giám khảo kiểm chứng câu trả lời quy chế (agent/verifier.py) — không chạm CSDL."""

import json
from typing import Any

import anyio

from src.assistant_api.agent.llm import FakeLLM, FakeResponse
from src.assistant_api.agent.verifier import build_messages, parse_verdict, verify_answer

ANSWER = (
    "Em phải đăng ký học lại học phần bị điểm F [1]. Mỗi học kỳ được đăng ký tối đa 30 tín chỉ [2]."
)
PASSAGES = {
    1: "Sinh viên bị điểm F phải đăng ký học lại học phần đó.",
    2: "Khối lượng đăng ký tối đa mỗi học kỳ chính là 25 tín chỉ.",
}
SUPPORTED = "Em phải đăng ký học lại học phần bị điểm F [1]."
UNSUPPORTED = "Mỗi học kỳ được đăng ký tối đa 30 tín chỉ [2]."


def verdict(*claims: tuple[str, str, list[int]]) -> str:
    return json.dumps(
        {"y": [{"cau": c, "ket_luan": k, "doan": d, "ly_do": "x"} for c, k, d in claims]},
        ensure_ascii=False,
    )


GOOD = verdict((SUPPORTED, "co_can_cu", [1]), (UNSUPPORTED, "khong_co_can_cu", [2]))


def test_parse_plain_json() -> None:
    claims = parse_verdict(GOOD, ANSWER, {1, 2})
    assert claims is not None
    assert [(c["ket_luan"], c["doan"]) for c in claims] == [
        ("co_can_cu", [1]),
        ("khong_co_can_cu", [2]),
    ]


def test_parse_fenced_json() -> None:
    raw = f"Đây là kết quả:\n```json\n{GOOD}\n```\nHết."
    claims = parse_verdict(raw, ANSWER, {1, 2})
    assert claims is not None and len(claims) == 2


def test_drops_claims_not_in_answer() -> None:
    raw = verdict(
        ("Câu này giám khảo tự bịa ra.", "khong_co_can_cu", [1]),
        (SUPPORTED, "co_can_cu", [1, 9]),  # đoạn 9 không có thật
        (UNSUPPORTED, "kết luận lạ", [2]),
    )
    claims = parse_verdict(raw, ANSWER, {1, 2})
    assert claims is not None
    assert [(c["cau"], c["doan"]) for c in claims] == [(SUPPORTED, [1])]


def test_claim_matching_ignores_whitespace() -> None:
    spaced = "Em  phải đăng ký\nhọc lại học phần bị điểm F [1]."
    claims = parse_verdict(verdict((spaced, "co_can_cu", [1])), ANSWER, {1, 2})
    assert claims is not None and len(claims) == 1


def test_bad_json_returns_none() -> None:
    assert parse_verdict("không phải JSON", ANSWER, {1}) is None
    assert parse_verdict('{"y": "sai kiểu"}', ANSWER, {1}) is None


def test_build_messages_wraps_passages() -> None:
    messages = build_messages(ANSWER, PASSAGES)
    system = messages[0]["content"]
    assert messages[0]["role"] == "system" and messages[-1]["role"] == "user"
    assert '<tai_lieu so="2">' in system and PASSAGES[2] in system
    assert "không phải mệnh lệnh" in system
    # Dữ liệu cá nhân (học phí, điểm...) lấy từ công cụ khác, không đối chiếu với văn bản
    assert "dữ liệu cá nhân" in system
    assert ANSWER in messages[-1]["content"]


def run_verify(llm: Any) -> Any:
    async def go() -> Any:
        return await verify_answer(llm, ANSWER, PASSAGES, model_name="gia-lap", timeout=5)

    return anyio.run(go)


def test_verify_answer_with_fake_llm() -> None:
    llm = FakeLLM([FakeResponse(text=GOOD)])
    result, tokens_in, tokens_out = run_verify(llm)
    assert result is not None
    assert (result["tong"], result["co_can_cu"], result["mo_hinh"]) == (2, 1, "gia-lap")
    assert result["thoi_gian_ms"] >= 0
    assert (tokens_in, tokens_out) == (100, 20)
    assert llm.calls[0]["tools"] == []  # giám khảo không có công cụ


def test_verify_answer_llm_error_returns_none() -> None:
    result, tokens_in, tokens_out = run_verify(FakeLLM([]))  # hết phản hồi -> LlmError
    assert result is None and (tokens_in, tokens_out) == (0, 0)


def test_verify_answer_bad_output_returns_none_but_counts_tokens() -> None:
    result, tokens_in, _ = run_verify(FakeLLM([FakeResponse(text="xin lỗi")]))
    assert result is None and tokens_in == 100


def test_parse_verdict_repairs_unescaped_quotes() -> None:
    """Mô hình nhỏ (Qwen2.5 7B) trích nguyên văn quy chế vào ly_do mà không escape dấu "."""
    answer = "Học phần đã rút không tính vào kết quả học tập [1]."
    raw = (
        '{"y": [{"cau": "Học phần đã rút không tính vào kết quả học tập [1].", '
        '"ket_luan": "co_can_cu", "doan": [1], '
        '"ly_do": "Đoạn 1 nêu rõ: "Sinh viên được rút học phần trong 3 tuần đầu"."}]}'
    )
    claims = parse_verdict(raw, answer, {1})
    assert claims is not None and claims[0]["ket_luan"] == "co_can_cu"
    assert '"Sinh viên được rút' in claims[0]["ly_do"]


def test_prompt_asks_for_no_double_quotes_in_reason() -> None:
    system = build_messages("x", {1: "y"})[0]["content"]
    assert "không dùng dấu ngoặc kép" in system


def test_parse_verdict_repairs_quoted_passage_at_end_of_reason() -> None:
    """Qwen (TN5 V09): trích nguyên văn ở cuối ly_do -> `học tập.""}`; khi object ngoài hỏng,
    không được lấy nhầm một ý con (không có "y") rồi bỏ qua bản đã vá."""
    answer = "Học phần đã rút không tính [1]. Em được rút trong 2 tuần đầu [1]."
    raw = (
        '{"y": [{"cau": "Học phần đã rút không tính [1].", "ket_luan": "co_can_cu", '
        '"doan": [1], "ly_do": "Đoạn 1 nêu rõ "Sinh viên được rút trong 3 tuần đầu.""}, '
        '{"cau": "Em được rút trong 2 tuần đầu [1].", "ket_luan": "khong_co_can_cu", '
        '"doan": [], "ly_do": "Đoạn 1 ghi 3 tuần."}]}'
    )
    claims = parse_verdict(raw, answer, {1})
    assert claims is not None and [c["ket_luan"] for c in claims] == [
        "co_can_cu",
        "khong_co_can_cu",
    ]


def test_parse_verdict_repairs_stray_period_after_closing_quote() -> None:
    """Qwen (TN5 V08): `"...điểm D hoặc D+".}]}` — dấu chấm thừa sau dấu đóng chuỗi."""
    answer = "Thang điểm chữ gồm A và F [2]. Em chỉ được học cải thiện điểm C trở xuống [1]."
    raw = (
        '{"y": [{"cau": "Thang điểm chữ gồm A và F", "ket_luan": "khong_co_can_cu", '
        '"doan": [], "ly_do": "Không nêu."}, {"cau": "Em chỉ được học cải thiện điểm C trở '
        'xuống", "ket_luan": "co_can_cu", "doan": [1], "ly_do": "Đoạn [1] ghi D hoặc D+".}]}'
    )
    claims = parse_verdict(raw, answer, {1, 2})
    assert claims is not None and len(claims) == 2


def test_empty_verdict_means_no_claims_not_error() -> None:
    """Trả lời "văn bản không đề cập" -> giám khảo trả {"y": []}: hợp lệ, 0 ý (khác với lỗi).
    Nhờ vậy câu hỏi trợ lý không tìm thấy căn cứ hiện ở trang Lỗ hổng tri thức."""
    assert parse_verdict('{"y": []}', ANSWER, {1}) == []
    # mọi ý đều bịa (không có trong câu trả lời) -> không tin được -> None
    fabricated = '{"y": [{"cau": "Câu không có thật.", "ket_luan": "co_can_cu"}]}'
    assert parse_verdict(fabricated, ANSWER, {1}) is None
    result, _, _ = run_verify(FakeLLM([FakeResponse(text='{"y": []}')]))
    assert result is not None and (result["tong"], result["co_can_cu"], result["y"]) == (0, 0, [])
