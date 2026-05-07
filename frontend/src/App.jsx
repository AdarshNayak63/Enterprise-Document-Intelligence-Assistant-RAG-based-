import { useState } from "react";
import { authApi } from "./api/client";
import ChatPage from "./pages/ChatPage";

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const formatApiError = (e, fallback = "Authentication failed") => {
    const detail = e?.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => item?.msg)
        .filter(Boolean)
        .join(", ") || fallback;
    }
    return fallback;
  };

  const handleAuth = async (mode) => {
    try {
      setError("");
      const fn = mode === "signup" ? authApi.signup : authApi.login;
      const { data } = await fn(email, password);
      localStorage.setItem("token", data.access_token);
      setToken(data.access_token);
    } catch (e) {
      setError(formatApiError(e));
    }
  };

  if (!token) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <h1>Enterprise RAG Assistant</h1>
          <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <p className="error">{error}</p>}
          <div className="row">
            <button onClick={() => handleAuth("login")}>Login</button>
            <button onClick={() => handleAuth("signup")}>Sign Up</button>
          </div>
        </div>
      </div>
    );
  }

  return <ChatPage onLogout={() => { localStorage.removeItem("token"); setToken(null); }} />;
}
