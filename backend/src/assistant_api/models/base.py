from sqlalchemy.orm import DeclarativeBase


class AssistantBase(DeclarativeBase):
    """Base cho CSDL `assistant`. Bảng do database/02_assistant_schema.sql tạo;
    KHÔNG gọi `AssistantBase.metadata.create_all()`."""
