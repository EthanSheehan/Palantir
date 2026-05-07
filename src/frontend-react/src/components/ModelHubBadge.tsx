import React, { useEffect, useState } from 'react';
import { Tag, Tooltip, Icon, IconName } from '@blueprintjs/core';
import { useSendMessage } from '../App';

/**
 * ModelHubBadge — header chip showing the live LLM provider chain.
 *
 * Reads `provider_status` from the backend (existing `LLMAdapter.get_provider_status`).
 * Displays as `gemini · ANT · ol` chips with the active provider highlighted.
 * Hover for full status (model names per provider). Updates every 30s and on
 * `grid-sentinel:provider-status` events.
 */

interface ProviderStatus {
  gemini: { available: boolean; models: Record<string, string> };
  anthropic: { available: boolean; models: Record<string, string> };
  ollama: { available: boolean; base_url: string; models: string[] };
  fallback_only: boolean;
}

const DEFAULT_STATUS: ProviderStatus = {
  gemini: { available: false, models: {} },
  anthropic: { available: false, models: {} },
  ollama: { available: false, base_url: '', models: [] },
  fallback_only: true,
};

export function ModelHubBadge() {
  const sendMessage = useSendMessage();
  const [status, setStatus] = useState<ProviderStatus>(DEFAULT_STATUS);
  // Most recent agent response — used to render which tier actually answered.
  const [lastResponse, setLastResponse] = useState<{
    provider?: string; model?: string; model_hint?: string;
  } | null>(null);

  useEffect(() => {
    function request() {
      sendMessage({ action: 'get_provider_status' });
    }
    request();
    const interval = setInterval(request, 30_000);
    function onResponse(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail) setStatus(detail as ProviderStatus);
    }
    function onAgentResponse(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail && detail.meta) {
        setLastResponse({
          provider: detail.meta.provider,
          model: detail.meta.model,
          model_hint: detail.meta.model_hint,
        });
      }
    }
    window.addEventListener('grid-sentinel:provider-status', onResponse);
    window.addEventListener('grid-sentinel:agent-response', onAgentResponse);
    return () => {
      clearInterval(interval);
      window.removeEventListener('grid-sentinel:provider-status', onResponse);
      window.removeEventListener('grid-sentinel:agent-response', onAgentResponse);
    };
  }, [sendMessage]);

  const chipStyle = (active: boolean, color: string) => ({
    fontSize: 9,
    padding: '0 5px',
    minHeight: 16,
    background: active ? `${color}33` : 'rgba(255,255,255,0.04)',
    color: active ? color : '#475569',
    border: `1px solid ${active ? color + '88' : 'rgba(255,255,255,0.08)'}`,
    fontFamily: 'monospace',
    letterSpacing: '0.06em',
  });

  const tooltipContent = (
    <div style={{ fontSize: 10, fontFamily: 'monospace', maxWidth: 240 }}>
      <div style={{ marginBottom: 4, color: '#e2e8f0', fontWeight: 700 }}>LLM PROVIDER CHAIN</div>
      <div>1. <span style={{ color: '#4285F4' }}>Gemini</span>: {status.gemini.available ? 'available' : 'offline'}</div>
      <div>2. <span style={{ color: '#D97757' }}>Anthropic</span>: {status.anthropic.available ? 'available' : 'offline'}</div>
      <div>3. <span style={{ color: '#7c3aed' }}>Ollama</span>: {status.ollama.available ? `${status.ollama.models.length} model(s)` : 'offline'}</div>
      <div>4. Heuristic: always</div>
      {status.fallback_only && (
        <div style={{ color: '#fbbf24', marginTop: 4 }}>⚠ Heuristic-only mode</div>
      )}
    </div>
  );

  // Tier label for the most recent agent response
  let tierColor = '#475569';
  if (lastResponse?.model_hint === 'reasoning') tierColor = '#a855f7';
  else if (lastResponse?.model_hint === 'fast') tierColor = '#22d3ee';
  else if (lastResponse?.model_hint === 'default') tierColor = '#94a3b8';

  return (
    <Tooltip content={tooltipContent} placement="bottom-end">
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <Icon icon={'predictive-analysis' as IconName} size={11} color="#94a3b8" />
        <Tag minimal style={chipStyle(status.gemini.available, '#4285F4')}>GEMINI</Tag>
        <Tag minimal style={chipStyle(status.anthropic.available, '#D97757')}>ANT</Tag>
        <Tag minimal style={chipStyle(status.ollama.available, '#7c3aed')}>OL</Tag>
        {status.fallback_only && (
          <Tag minimal style={{ ...chipStyle(true, '#fbbf24'), marginLeft: 2 }}>HEURISTIC</Tag>
        )}
        {lastResponse && lastResponse.model_hint && (
          <Tag minimal style={{
            fontSize: 9,
            padding: '0 5px',
            minHeight: 16,
            background: `${tierColor}22`,
            color: tierColor,
            border: `1px solid ${tierColor}55`,
            fontFamily: 'monospace',
            letterSpacing: '0.04em',
            marginLeft: 4,
          }}>
            {lastResponse.model ? `${lastResponse.model} · ${lastResponse.model_hint}` : lastResponse.model_hint}
          </Tag>
        )}
      </div>
    </Tooltip>
  );
}
