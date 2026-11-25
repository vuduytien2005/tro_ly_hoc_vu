"""System prompt: chỉ dẫn tra cứu bao gồm cả kho hỏi đáp cán bộ (TN6, 25/11/2026)."""

from src.assistant_api.agent.prompts import SYSTEM_PROMPT


def test_prompt_requires_search_for_student_life_questions() -> None:
    # TN6: trợ lý trả lời luôn câu hỏi giờ căn tin / giá in tài liệu mà không tra cứu
    assert "đời sống, dịch vụ sinh viên" in SYSTEM_PROMPT


def test_prompt_treats_staff_answers_as_a_source() -> None:
    # TN6: đoạn kho đứng hạng 1 nhưng trợ lý vẫn nói "văn bản quy chế không đề cập"
    assert "Hỏi đáp cán bộ" in SYSTEM_PROMPT
    assert "trích dẫn như văn bản" in SYSTEM_PROMPT
