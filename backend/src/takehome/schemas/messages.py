from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CitationOut(BaseModel):
    id: str
    document_id: str
    document_name: str
    page_number: int
    clause: str | None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sources_cited: int
    message_type: str = "chat"
    citations: list[CitationOut] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str
