import React from "react";
import "./ResultPanel.css";
import { REQUEST_TYPES } from "./CodeForm";

function typeLabel(value) {
  return REQUEST_TYPES.find((t) => t.value === value)?.label ?? value;
}

export default function ResultPanel({ loading, result }) {
  return (
    <section className="result-panel">
      <h2>🎯 LLM Analysis Result</h2>

      <div className="result-output">
        {loading
          ? "Analyzing code with LLM..."
          : result?.analysis_result ??
            "Ready for analysis. Submit code from the left panel."}
      </div>

      {result && (
        <div className="result-metadata">
          <div className="metadata-item">
            <span>Status:</span>
            <span
              className={`status-badge status-${String(
                result.status
              ).toLowerCase()}`}
            >
              {result.status}
            </span>
          </div>
          <div className="metadata-item">
            <span>Analysis ID:</span>
            <span>{result.id}</span>
          </div>
          <div className="metadata-item">
            <span>Analysis Type:</span>
            <span>{typeLabel(result.request_type)}</span>
          </div>
          <div className="metadata-item">
            <span>Language:</span>
            <span>{result.original_code ? "Code provided" : "N/A"}</span>
          </div>
          <div className="metadata-item">
            <span>Timestamp:</span>
            <span>
              {result.timestamp
                ? new Date(result.timestamp).toLocaleString()
                : "-"}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
