import React from "react";
import "./CodeForm.css";

const REQUEST_TYPES = [
  { value: "documentation", label: "Documentation Generation" },
  { value: "review", label: "Code Review" },
  { value: "optimization", label: "Optimization Suggestions" },
  { value: "bug_fix", label: "Bug Analysis" },
];

const LANGUAGES = [
  { value: "python", label: "Python" },
  { value: "java", label: "Java" },
];

export default function CodeForm({
  language,
  setLanguage,
  requestType,
  setRequestType,
  code,
  setCode,
  prompt,
  setPrompt,
  loading,
  onAnalyze,
  onClear,
}) {
  return (
    <section className="code-form">
      <h2>📝 Code Input</h2>

      <div className="form-group">
        <label htmlFor="language">Programming Language</label>
        <select
          id="language"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          {LANGUAGES.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label htmlFor="requestType">Analysis Type</label>
        <select
          id="requestType"
          value={requestType}
          onChange={(e) => setRequestType(e.target.value)}
        >
          {REQUEST_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label htmlFor="codeInput">Paste Your Code</label>
        <textarea
          id="codeInput"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="Paste your code here..."
        />
      </div>

      <div className="form-group">
        <label htmlFor="prompt">Additional Instructions (optional)</label>
        <input
          id="prompt"
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g., Focus on performance optimization..."
        />
      </div>

      <div className="button-group">
        <button className="btn btn-primary" onClick={onAnalyze} disabled={loading}>
          {loading ? "Analyzing..." : "🔍 Analyze Code"}
        </button>
        <button className="btn btn-secondary" onClick={onClear}>
          Clear
        </button>
      </div>
    </section>
  );
}

export { REQUEST_TYPES };
