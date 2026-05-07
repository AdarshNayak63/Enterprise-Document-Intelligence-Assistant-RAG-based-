import axios from "axios";

const API_BASE = "http://localhost:5000";

const client = axios.create({ baseURL: API_BASE });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authApi = {
  signup: (email, password) => client.post("/api/auth/signup", { email, password }),
  login: (email, password) => client.post("/api/auth/login", { email, password })
};

export const docsApi = {
  upload: (file, sessionId) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("session_id", String(sessionId));
    return client.post("/api/documents/upload", fd);
  },
  list: (sessionId) => {
    if (sessionId) return client.get("/api/documents", { params: { session_id: sessionId } });
    return client.get("/api/documents");
  }
};

export const chatApi = {
  query: (payload) => client.post("/api/chat/query", payload),
  createSession: (payload) => client.post("/api/chat/sessions", payload),
  sessions: () => client.get("/api/chat/sessions"),
  messages: (sessionId) => client.get(`/api/chat/sessions/${sessionId}/messages`),
  deleteSession: (sessionId) => client.delete(`/api/chat/sessions/${sessionId}`)
};
