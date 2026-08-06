import React from "react";
import "./HistoryList.css";
import { REQUEST_TYPES } from "./CodeForm";

function typeLabel(value) {
  return REQUEST_TYPES.find((t) => t.value === value)?.label ?? value;
}

export default function HistoryList({ history, onSelect }) {
  return (
    <section className="history-list">
      <h3>📚 Analysis History</h3>

      {history.length === 0 ? (
        <p className="history-empty">No analyses yet...</p>
      ) : (
        history.slice(0, 5).map((item) => (
          <button
            key={item.id}
            className="history-item"
            onClick={() => onSelect(item.id)}
          >
            <strong>{typeLabel(item.request_type)}</strong>
            <br />
            <small>
              ID: {String(item.id).slice(0, 8)}... |{" "}
              {item.timestamp
                ? new Date(item.timestamp).toLocaleTimeString()
                : "-"}
            </small>
          </button>
        ))
      )}
    </section>
  );
}
