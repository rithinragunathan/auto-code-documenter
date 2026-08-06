import React, { useState, useEffect, useCallback } from "react";
import "./App.css";
import Header from "./components/Header";
import CodeForm from "./components/CodeForm";
import ResultPanel from "./components/ResultPanel";
import HistoryList from "./components/HistoryList";

const API_BASE_URL = "http://localhost:8080";

export default function App() {
  const [language, setLanguage] = useState("python");
  const [requestType, setRequestType] = useState("documentation");
  const [code, setCode] = useState("");
  const [prompt, setPrompt] = useState("");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [history, setHistory] = useState([]);
  const [serverStatus, setServerStatus] = useState("checking");

  const checkServerHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/health`);
      if (!res.ok) throw new Error("bad status");
      await res.json();
      setServerStatus("connected");
    } catch {
      setServerStatus("disconnected");
      setError(
        "Cannot connect to backend server. Make sure Spring Boot is running on port 8080."
      );
    }
  }, []);

  useEffect(() => {
    checkServerHealth();
  }, [checkServerHealth]);

  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(""), 5000);
    return () => clearTimeout(t);
  }, [error]);

  useEffect(() => {
    if (!success) return;
    const t = setTimeout(() => setSuccess(""), 3000);
    return () => clearTimeout(t);
  }, [success]);

  const analyzeCode = async () => {
    const trimmed = code.trim();
    if (!trimmed) {
      setError("Please enter some code to analyze");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    const requestBody = { code: trimmed, language, request_type: requestType, prompt };

    try {
      const res = await fetch(`${API_BASE_URL}/api/analyze-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });

      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

      const data = await res.json();
      setResult(data);
      setHistory((prev) => [data, ...prev]);
      setSuccess("Analysis completed successfully!");
    } catch (err) {
      setError("Error analyzing code: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const clearInput = () => {
    setCode("");
    setPrompt("");
    setResult(null);
  };

  const loadHistoryItem = (id) => {
    const item = history.find((h) => h.id === id);
    if (item) setResult(item);
  };

  return (
    <div className="app">
      <Header serverStatus={serverStatus} />

      {error && <div className="banner banner-error">{error}</div>}
      {success && <div className="banner banner-success">{success}</div>}

      <div className="app-grid">
        <CodeForm
          language={language}
          setLanguage={setLanguage}
          requestType={requestType}
          setRequestType={setRequestType}
          code={code}
          setCode={setCode}
          prompt={prompt}
          setPrompt={setPrompt}
          loading={loading}
          onAnalyze={analyzeCode}
          onClear={clearInput}
        />

        <div className="app-right">
          <ResultPanel loading={loading} result={result} />
          <HistoryList history={history} onSelect={loadHistoryItem} />
        </div>
      </div>
    </div>
  );
}
