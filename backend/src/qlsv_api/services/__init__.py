"""Tầng nghiệp vụ: nhận Session + tham số thuần Python, trả schema hoặc ném BusinessError.

Không import FastAPI -> dùng lại được từ script, test, hay giao diện khác.
Mọi so sánh thời gian dùng tham số `now` (lấy từ src.shared.time.now() ở tầng router).
"""
