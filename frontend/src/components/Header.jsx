import React from "react";
import "./Header.css";

export default function Header({ serverStatus }) {
  const statusText =
    serverStatus === "connected"
      ? "✅ Connected"
      : serverStatus === "disconnected"
      ? "❌ Disconnected"
      : "Checking...";

  return (
    <header className="header">
      <h1>🚀 AutoDocx</h1>
      <p>Code analysis powered by an LLM</p>
      <p className={`server-status server-status--${serverStatus}`}>
        Server: {statusText}
      </p>
    </header>
  );
}
