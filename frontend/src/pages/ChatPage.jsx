import { useEffect, useState } from "react";
import { chatApi, docsApi } from "../api/client";

export default function ChatPage({ onLogout }) {
  const [docs, setDocs] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [sessionDocs, setSessionDocs] = useState([]);
  const [isAsking, setIsAsking] = useState(false);

  const loadAll = async () => {
    const { data: s } = await chatApi.sessions();
    setSessions(s);
  };

  useEffect(() => {
    loadAll();
  }, []);

  const loadSessionDocs = async (sid) => {
    if (!sid) {
      setDocs([]);
      return;
    }
    const { data } = await docsApi.list(sid);
    setDocs(data);
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!sessionId) return;
    await docsApi.upload(file, sessionId);
    await Promise.all([loadAll(), loadSessionDocs(sessionId)]);
  };

  const loadMessages = async (sid) => {
    const { data } = await chatApi.messages(sid);
    const targetSession = sessions.find((s) => s.id === sid);
    setSessionId(sid);
    setSessionDocs(targetSession?.document_ids || []);
    await loadSessionDocs(sid);
    setMessages(
      data.map((m) => ({
        role: m.role,
        content: m.content,
        citations: m.citations_json ? JSON.parse(m.citations_json) : []
      }))
    );
  };

  const ask = async () => {
    if (!query.trim() || !sessionId || isAsking) return;
    const userMsg = { role: "user", content: query, citations: [] };
    setMessages((prev) => [...prev, userMsg]);
    const payload = { query, session_id: sessionId, document_ids: sessionDocs };
    setQuery("");
    setIsAsking(true);
    try {
      const { data } = await chatApi.query(payload);
      setSessionId(data.session_id);
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer, citations: data.citations }]);
      await loadAll();
    } catch (err) {
      const apiError = err?.response?.data?.detail || "Failed to get a response from backend/LLM.";
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${apiError}`, citations: [] }]);
    } finally {
      setIsAsking(false);
    }
  };

  const createNewSession = async () => {
    const { data } = await chatApi.createSession({ title: "New Chat", document_ids: [] });
    await loadAll();
    setSessionId(data.id);
    setSessionDocs(data.document_ids || []);
    await loadSessionDocs(data.id);
    setMessages([]);
    setQuery("");
  };

  const deleteSession = async (sid) => {
    await chatApi.deleteSession(sid);
    setSessions((prev) => prev.filter((s) => s.id !== sid));
    if (sessionId === sid) {
      setSessionId(null);
      setSessionDocs([]);
      setDocs([]);
      setMessages([]);
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h3>Chats</h3>
        <div className="new-chat-box">
          <strong>Start a fresh chat</strong>
          <button onClick={createNewSession}>New Chat</button>
        </div>
        {sessions.map((s) => (
          <div key={s.id} className="session-row">
            <button className="session" onClick={() => loadMessages(s.id)}>
              {s.title}
            </button>
            <button className="delete-session" onClick={() => deleteSession(s.id)} title="Delete chat">
              Delete
            </button>
          </div>
        ))}
        <button className="logout-btn" onClick={onLogout}>Logout</button>
      </aside>
      <main className="chat-main">
        <header>
          <h2>Document Intelligence Assistant</h2>
          <input type="file" onChange={upload} disabled={!sessionId} />
          <div className="docs-row">
            <strong>Documents for this chat:</strong>
            {!sessionId && <span>Create/select a chat first</span>}
            {sessionId && docs.length === 0 && <span>No documents attached</span>}
            {docs.map((doc) => <span key={doc.id} className="doc-chip">{doc.filename}</span>)}
          </div>
        </header>
        <section className="messages">
          {messages.map((m, idx) => (
            <div key={idx} className={`msg ${m.role}`}>
              <p>{m.content}</p>
              {m.citations?.length > 0 && (
                <div className="citations">
                  {m.citations.map((c, i) => (
                    <small key={i}>[{c.filename} | p.{c.page_number} | chunk {c.chunk_id}]</small>
                  ))}
                </div>
              )}
            </div>
          ))}
          {isAsking && (
            <div className="msg assistant loading-msg">
              <div className="loading-dots" aria-label="Getting response">
                <span />
                <span />
                <span />
              </div>
              <p>Getting response from backend/LLM...</p>
            </div>
          )}
        </section>
        <footer>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={!sessionId || isAsking}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask();
              }
            }}
            placeholder="Ask a question..."
          />
          <button onClick={ask} disabled={!sessionId || isAsking || !query.trim()}>
            {isAsking ? "Sending..." : "Send"}
          </button>
        </footer>
      </main>
    </div>
  );
}
