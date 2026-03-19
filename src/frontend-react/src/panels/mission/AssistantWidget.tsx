import React, { useRef, useEffect } from 'react';
import { useSimStore } from '../../store/SimulationStore';
import { SEVERITY_STYLES } from '../../shared/constants';

export function AssistantWidget() {
  const messages = useSimStore(s => s.assistantMessages);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, letterSpacing: '0.05em' }}>
        TACTICAL AIP ASSISTANT
      </div>
      <div
        ref={logRef}
        style={{ maxHeight: 200, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}
      >
        {messages.length === 0 && (
          <div style={{ color: '#94a3b8', fontSize: 12 }}>Waiting for intel...</div>
        )}
        {messages.map((msg, i) => {
          const style = SEVERITY_STYLES[msg.severity] || SEVERITY_STYLES.INFO;
          return (
            <div
              key={i}
              style={{ borderLeft: `3px solid ${style.border}`, paddingLeft: 8, fontSize: 13 }}
            >
              <span style={{ color: style.color, fontSize: 11 }}>[{msg.timestamp}]</span>{' '}
              {msg.text}
            </div>
          );
        })}
      </div>
    </div>
  );
}
