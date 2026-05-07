from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional


class Citation(BaseModel):
    document_id: int
    filename: str
    page_number: int
    chunk_id: int
    snippet: str


class ChatRequest(BaseModel):
    query: str
    session_id: Optional[int] = None
    document_ids: Optional[List[int]] = None


class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Chat"
    document_ids: Optional[List[int]] = None


class ChatResponse(BaseModel):
    session_id: int
    answer: str
    citations: List[Citation]


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    citations_json: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    id: int
    title: str
    document_ids: List[int] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True
