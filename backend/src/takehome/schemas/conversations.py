from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentInfo(BaseModel):
    id: str
    filename: str
    page_count: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    has_document: bool
    document_count: int

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    has_document: bool
    document_count: int
    documents: list[DocumentInfo] = []

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    pass


class ConversationUpdate(BaseModel):
    title: str
