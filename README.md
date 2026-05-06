# Enterprise Document Intelligence Assistant (RAG-based)

Production-oriented multi-document RAG assistant using FastAPI, FAISS, PostgreSQL, React, and Ollama.

## Features
- JWT auth: signup/login
- Multi-format ingestion: PDF, DOCX, CSV, TXT
- Chunking with overlap
- Embeddings via sentence-transformers
- FAISS semantic retrieval (per-user local index)
- RAG generation via Ollama open-source LLM
- Multi-turn chat with persisted chat sessions/messages
- Source attribution (filename, page, chunk)
- Multi-document filtering in query flow

## Architecture
- Backend: `FastAPI` + `SQLAlchemy`
- LLM runtime: `Ollama` (`/api/chat`)
- Vector store: `FAISS`
- Metadata/chat store: `PostgreSQL` (SQLite supported for local quickstart)
- Frontend: `React + Vite`

## Backend setup (local)
```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# update .env values if needed
uvicorn app.main:app --reload --port 5000
```

## Ollama setup
```bash
ollama pull llama3.1:8b
ollama serve
```

## Frontend setup
```bash
cd frontend
npm install
npm run dev
```

## Docker setup
```bash
docker compose up --build
```

Then open:
- API docs: `http://localhost:5000/docs`
- UI: `http://localhost:5173`

## API Endpoints
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/documents/upload`
- `GET /api/documents`
- `POST /api/chat/query`
- `GET /api/chat/sessions`
- `GET /api/chat/sessions/{session_id}/messages`

## Security and production hardening checklist
- Replace `SECRET_KEY` with strong random key.
- Restrict CORS origins.
- Add request size limits and MIME validation.
- Add background workers for ingestion and OCR enhancements.
- Add rate limiting and structured audit logs.
- Add SSO/RBAC and tenant isolation for enterprise scenarios.
- Add encryption-at-rest for file/object storage.
- Deploy managed Postgres and distributed vector DB for scale.

## Notes
- Current FAISS mode is per-user local index files in `backend/storage/faiss`.
- For larger scale, swap vector layer with Milvus/Weaviate/Qdrant and async ingestion pipeline.
# Enterprise-Document-Intelligence-Assistant-RAG-based-
