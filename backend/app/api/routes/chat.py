import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import httpx

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.models.document import Document
from app.models.session_document import SessionDocument
from app.schemas.chat import ChatRequest, ChatResponse, ChatSessionResponse, ChatMessageResponse, ChatSessionCreate
from app.services.vector_store import vector_store
from app.services.llm import generate_answer, citations_from_chunks, dump_citations, LLMServiceError

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _allowed_doc_ids(db: Session, user_id: int) -> list[int]:
    return [d.id for d in db.query(Document.id).filter(Document.user_id == user_id).all()]


def _session_doc_ids(db: Session, session_id: int) -> list[int]:
    return [
        row.document_id
        for row in db.query(SessionDocument.document_id).filter(SessionDocument.session_id == session_id).all()
    ]


def _attach_docs_to_session(db: Session, session_id: int, doc_ids: list[int]) -> None:
    if not doc_ids:
        return
    db.add_all([SessionDocument(session_id=session_id, document_id=doc_id) for doc_id in doc_ids])


@router.post("/sessions", response_model=ChatSessionResponse)
def create_session(
    payload: ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    requested_doc_ids = payload.document_ids or []
    allowed_doc_ids = _allowed_doc_ids(db, current_user.id)
    for doc_id in requested_doc_ids:
        if doc_id not in allowed_doc_ids:
            raise HTTPException(status_code=403, detail=f"Unauthorized document: {doc_id}")

    session = ChatSession(user_id=current_user.id, title=(payload.title or "New Chat")[:255])
    db.add(session)
    db.commit()
    db.refresh(session)

    _attach_docs_to_session(db, session.id, requested_doc_ids)
    db.commit()

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        document_ids=requested_doc_ids,
    )


@router.post("/query", response_model=ChatResponse)
async def query_chat(payload: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = None
    session_doc_ids: list[int] = []
    if payload.session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == payload.session_id, ChatSession.user_id == current_user.id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_doc_ids = _session_doc_ids(db, session.id)
    else:
        session = ChatSession(user_id=current_user.id, title=payload.query[:60] or "New Chat")
        db.add(session)
        db.commit()
        db.refresh(session)
        requested_doc_ids = payload.document_ids or []
        allowed_doc_ids = _allowed_doc_ids(db, current_user.id)
        for doc_id in requested_doc_ids:
            if doc_id not in allowed_doc_ids:
                raise HTTPException(status_code=403, detail=f"Unauthorized document: {doc_id}")
        _attach_docs_to_session(db, session.id, requested_doc_ids)
        db.commit()
        session_doc_ids = requested_doc_ids

    chunks = vector_store.search(current_user.id, payload.query, top_k=5, doc_ids=session_doc_ids)
    history_rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    try:
        answer = await generate_answer(payload.query, chunks, history)
    except LLMServiceError as exc:
        detail = str(exc) or "LLM backend error."
        if "requires more system memory" in detail:
            raise HTTPException(
                status_code=503,
                detail=(
                    "LLM does not have enough RAM to run the selected model. "
                    "Close memory-heavy apps or install/use a smaller Ollama model (for example: phi3:mini). "
                    f"Ollama error: {detail}"
                ),
            )
        raise HTTPException(status_code=502, detail=f"LLM request failed: {detail}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM timed out. Please try a shorter question or retry.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}")
    citations = citations_from_chunks(chunks)

    db.add(ChatMessage(session_id=session.id, role="user", content=payload.query, citations_json="[]"))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=answer, citations_json=dump_citations(citations)))
    db.commit()

    return ChatResponse(session_id=session.id, answer=answer, citations=citations)


@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return [
        ChatSessionResponse(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            document_ids=_session_doc_ids(db, s.id),
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_session_messages(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.query(SessionDocument).filter(SessionDocument.session_id == session_id).delete()
    # Explicitly delete messages first so behavior is consistent across DB engines.
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    return {"status": "deleted", "session_id": session_id}
