import React, { useEffect, useRef, useState } from 'react';
import { Button, Icon, IconName, Tag, InputGroup } from '@blueprintjs/core';
import { useSendMessage } from '../App';
import { ModelHubBadge } from '../components/ModelHubBadge';

/**
 * AIPChatPanel — natural-language operator chat that routes to all 9 agents.
 *
 * Slash commands:
 *   /isr        ISR Observer — sensor fusion
 *   /strategy   Strategy Analyst — ROE evaluation, priority
 *   /tactics    Tactical Planner — COA generation
 *   /effects    Effectors Agent — engagement & BDA
 *   /pattern    Pattern Analyzer
 *   /tasking    AI Tasking Manager — sensor retasking
 *   /battlespace  Battlespace Manager
 *   /sitrep     Synthesis Query Agent — NL queries / SITREP
 *   /audit      Performance Auditor
 *
 * Free text routes through `synthesis_query_agent` which classifies & dispatches.
 */

const AGENTS = [
  { slash: '/isr',        agent: 'isr_observer',          color: '#22d3ee', label: 'ISR' },
  { slash: '/strategy',   agent: 'strategy_analyst',      color: '#fbbf24', label: 'STRAT' },
  { slash: '/tactics',    agent: 'tactical_planner',      color: '#a855f7', label: 'TAC' },
  { slash: '/effects',    agent: 'effectors_agent',       color: '#ef4444', label: 'EFX' },
  { slash: '/pattern',    agent: 'pattern_analyzer',      color: '#7ED321', label: 'PAT' },
  { slash: '/tasking',    agent: 'ai_tasking_manager',    color: '#06b6d4', label: 'TASK' },
  { slash: '/battlespace', agent: 'battlespace_manager',  color: '#fb923c', label: 'BSM' },
  { slash: '/sitrep',     agent: 'synthesis_query_agent', color: '#94a3b8', label: 'SIT' },
  { slash: '/audit',      agent: 'performance_auditor',   color: '#cbd5e1', label: 'AUD' },
];

interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system';
  agent?: string;
  agentColor?: string;
  text: string;
  timestamp: number;
  meta?: Record<string, any>;
}

interface Props { visible: boolean; onClose: () => void; }

export function AIPChatPanel({ visible, onClose }: Props) {
  const sendMessage = useSendMessage();
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: 'sys-0',
    role: 'system',
    text: 'AIP ready. Type a question or use a slash-command (/isr, /tactics, /sitrep, …).',
    timestamp: Date.now(),
  }]);
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onAgentResponse(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (!detail) return;
      const agent = AGENTS.find(a => a.agent === detail.agent);
      setMessages(m => [...m, {
        id: detail.id ?? `r-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`,
        role: 'agent',
        agent: detail.agent ?? 'agent',
        agentColor: agent?.color ?? '#94a3b8',
        text: detail.text ?? JSON.stringify(detail, null, 2),
        timestamp: Date.now(),
        meta: detail.meta,
      }]);
    }
    window.addEventListener('grid-sentinel:agent-response', onAgentResponse);
    return () => window.removeEventListener('grid-sentinel:agent-response', onAgentResponse);
  }, []);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  if (!visible) return null;

  function send() {
    const text = input.trim();
    if (!text) return;
    let agentKey = 'synthesis_query_agent';
    let body = text;
    for (const a of AGENTS) {
      if (text.startsWith(a.slash)) {
        agentKey = a.agent;
        body = text.slice(a.slash.length).trim();
        break;
      }
    }
    setMessages(m => [...m, {
      id: `u-${Date.now()}`,
      role: 'user',
      text,
      timestamp: Date.now(),
    }]);
    sendMessage({ action: 'agent_query', agent: agentKey, query: body });
    setInput('');
  }

  return (
    <div
      role="dialog"
      aria-label="AIP chat"
      style={{
        position: 'fixed',
        right: 12,
        bottom: 12,
        width: 380,
        height: 460,
        background: 'rgba(7, 11, 17, 0.97)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 4,
        boxShadow: '-8px 8px 32px rgba(0,0,0,0.55)',
        zIndex: 8400,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        background: 'rgba(15, 20, 30, 0.95)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon icon={'predictive-analysis' as IconName} size={12} color="#a855f7" />
          <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 11, letterSpacing: '0.16em', color: '#e2e8f0' }}>
            AIP CHAT
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <ModelHubBadge />
          <Button minimal small icon={'cross' as IconName} onClick={onClose} aria-label="Close" />
        </div>
      </div>

      {/* Agent legend */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 4,
        padding: '6px 8px',
        background: 'rgba(15, 20, 30, 0.6)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        {AGENTS.map(a => (
          <button
            key={a.agent}
            onClick={() => setInput(a.slash + ' ')}
            title={a.agent}
            style={{
              fontSize: 9,
              fontFamily: 'monospace',
              padding: '2px 5px',
              border: `1px solid ${a.color}55`,
              background: `${a.color}22`,
              color: a.color,
              borderRadius: 2,
              cursor: 'pointer',
              letterSpacing: '0.04em',
            }}
          >{a.slash}</button>
        ))}
      </div>

      {/* Scroll area */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
        {messages.map(m => (
          <MessageRow key={m.id} message={m} />
        ))}
      </div>

      {/* Input */}
      <div style={{
        padding: '6px 8px',
        borderTop: '1px solid rgba(255,255,255,0.07)',
        background: 'rgba(15, 20, 30, 0.95)',
      }}>
        <InputGroup
          value={input}
          onChange={(e: any) => setInput(e.target.value)}
          onKeyDown={(e: any) => { if (e.key === 'Enter') send(); }}
          placeholder="/sitrep status of all SAM threats…"
          rightElement={<Button minimal small icon={'send-message' as IconName} onClick={send} />}
          small
        />
      </div>
    </div>
  );
}

function MessageRow({ message }: { message: ChatMessage }) {
  if (message.role === 'system') {
    return (
      <div style={{ fontSize: 10, color: '#475569', fontStyle: 'italic', marginBottom: 6 }}>
        {message.text}
      </div>
    );
  }
  const isUser = message.role === 'user';
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 6,
    }}>
      <div style={{
        display: 'flex',
        gap: 4,
        alignItems: 'center',
        marginBottom: 2,
      }}>
        <span style={{ fontSize: 9, color: '#475569' }}>
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
        {message.agent && (
          <Tag minimal style={{
            fontSize: 8,
            background: `${message.agentColor ?? '#94a3b8'}22`,
            color: message.agentColor ?? '#94a3b8',
            border: `1px solid ${message.agentColor ?? '#94a3b8'}44`,
            padding: '0 4px',
            minHeight: 14,
          }}>{message.agent}</Tag>
        )}
      </div>
      <div style={{
        maxWidth: '88%',
        padding: '6px 8px',
        borderRadius: 3,
        background: isUser ? 'rgba(34, 211, 238, 0.12)' : 'rgba(255,255,255,0.04)',
        border: `1px solid ${isUser ? 'rgba(34, 211, 238, 0.25)' : 'rgba(255,255,255,0.08)'}`,
        color: '#e2e8f0',
        fontSize: 11,
        lineHeight: 1.42,
        whiteSpace: 'pre-wrap',
      }}>
        {message.text}
      </div>
    </div>
  );
}
