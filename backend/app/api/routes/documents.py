import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.chat import ChatSession
from app.models.session_document import SessionDocument
from app.schemas.document import DocumentResponse
from app.services.parsers import parse_pdf, parse_docx, parse_csv, parse_xlsx, parse_txt
from app.utils.chunker import chunk_text
from app.services.vector_store import vector_store

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXT = {".pdf", ".docx", ".csv", ".xlsx", ".txt"}


def extract_text_pages(path: str, ext: str):
    if ext == ".pdf":
        return parse_pdf(path)
    if ext == ".docx":
        return parse_docx(path)
    if ext == ".csv":
        return parse_csv(path)
    if ext == ".xlsx":
        return parse_xlsx(path)
    if ext == ".txt":
        return parse_txt(path)
    return []


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    session_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    user_dir = os.path.join(settings.upload_dir, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4()}_{file.filename}"
    path = os.path.join(user_dir, safe_name)

    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    doc = Document(user_id=current_user.id, filename=file.filename, file_path=path, file_type=ext)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    pages = extract_text_pages(path, ext)
    chunk_records = []
    for page_number, text in pages:
        chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        for idx, chunk in enumerate(chunks):
            ck = Chunk(document_id=doc.id, chunk_index=idx, page_number=page_number, content=chunk)
            db.add(ck)
            db.flush()
            chunk_records.append(
                {
                    "chunk_id": ck.id,
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "page_number": page_number,
                    "content": chunk,
                }
            )
    db.commit()
    vector_store.add_chunks(current_user.id, chunk_records)

    # Bind uploaded document to the current chat session.
    db.add(SessionDocument(session_id=session_id, document_id=doc.id))
    db.commit()

    return doc


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    session_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return (
            db.query(Document)
            .join(SessionDocument, SessionDocument.document_id == Document.id)
            .filter(SessionDocument.session_id == session_id, Document.user_id == current_user.id)
            .order_by(Document.created_at.desc())
            .all()
        )

    return (
        db.query(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
