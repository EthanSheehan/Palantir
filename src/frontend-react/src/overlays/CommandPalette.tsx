import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useSimStore } from '../store/SimulationStore';
import { useSendMessage } from '../App';

const HISTORY_KEY = 'palantir:cmd_history';
const MAX_HISTORY = 5;
const MAP_MODES = ['OPERATIONAL', 'COVERAGE', 'THREAT', 'FUSION', 'SWARM', 'TERRAIN'] as const;

interface Command {
  id: string;
  label: string;
  category: 'UAV' | 'Targets' | 'Map' | 'System';
  shortcut?: string;
  action: () => void;
}

function loadHistory(): string[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? '[]');
  } catch {
    return [];
  }
}

function saveHistory(id: string) {
  const prev = loadHistory().filter((h) => h !== id);
  localStorage.setItem(HISTORY_KEY, JSON.stringify([id, ...prev].slice(0, MAX_HISTORY)));
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function CommandPalette({ isOpen, onClose }: Props) {
  const sendMessage = useSendMessage();
  const uavs = useSimStore((s) => s.uavs);
  const targets = useSimStore((s) => s.targets);
  const autonomyLevel = useSimStore((s) => s.autonomyLevel);
  const setMapMode = useSimStore((s) => s.setMapMode);

  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const [history, setHistory] = useState<string[]>(() => loadHistory());
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Build command list dynamically
  const commands: Command[] = [
    // UAV commands
    ...uavs.map((uav) => ({
      id: `follow-uav-${uav.id}`,
      label: `Follow UAV ${uav.id} (${uav.mode})`,
      category: 'UAV' as const,
      action: () => sendMessage({ action: 'follow_target', drone_id: uav.id }),
    })),
    // Target approval commands
    ...targets
      .filter((t) => t.status === 'NOMINATED')
      .map((t) => ({
        id: `approve-${t.id}`,
        label: `Approve Nomination: ${t.target_type} #${t.id}`,
        category: 'Targets' as const,
        action: () => sendMessage({ action: 'approve_nomination', target_id: t.id }),
      })),
    // Map mode commands
    ...MAP_MODES.map((mode) => ({
      id: `map-mode-${mode}`,
      label: `Map Mode: ${mode}`,
      category: 'Map' as const,
      shortcut: String(MAP_MODES.indexOf(mode) + 1),
      action: () => setMapMode(mode),
    })),
    // Autonomy commands
    {
      id: 'autonomy-manual',
      label: 'Set Autonomy: MANUAL',
      category: 'System',
      action: () => sendMessage({ action: 'set_autonomy_level', level: 'MANUAL' }),
    },
    {
      id: 'autonomy-supervised',
      label: 'Set Autonomy: SUPERVISED',
      category: 'System',
      action: () => sendMessage({ action: 'set_autonomy_level', level: 'SUPERVISED' }),
    },
    {
      id: 'autonomy-autonomous',
      label: 'Set Autonomy: AUTONOMOUS (use sidebar toggle)',
      category: 'System',
      action: () => {
        // AUTONOMOUS requires the briefing dialog confirmation — close palette
        // so the operator uses the AutonomyToggle which enforces the safety gate
        onClose();
      },
    },
    {
      id: 'reset-sim',
      label: 'Reset Simulation',
      category: 'System',
      action: () => sendMessage({ action: 'reset' }),
    },
  ];

  // Filter by query; if empty, show history first
  const filtered = query.trim()
    ? commands.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()))
    : [
        ...history
          .map((id) => commands.find((c) => c.id === id))
          .filter((c): c is Command => !!c),
        ...commands.filter((c) => !history.includes(c.id)),
      ];

  // Reset selection when filter changes
  useEffect(() => {
    setActiveIdx(0);
  }, [query]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setActiveIdx(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const execute = useCallback(
    (cmd: Command) => {
      cmd.action();
      saveHistory(cmd.id);
      setHistory(loadHistory());
      onClose();
    },
    [onClose]
  );

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, filtered.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        const cmd = filtered[activeIdx];
        if (cmd) execute(cmd);
        return;
      }
    }

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, filtered, activeIdx, execute, onClose]);

  // Scroll active item into view
  useEffect(() => {
    const el = listRef.current?.children[activeIdx] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIdx]);

  if (!isOpen) return null;

  const CATEGORY_COLORS: Record<string, string> = {
    UAV: '#3b82f6',
    Targets: '#ef4444',
    Map: '#10b981',
    System: '#f59e0b',
  };

  return (
    /* Backdrop */
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9000,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: 80,
      }}
    >
      {/* Panel */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 560,
          maxHeight: 480,
          background: 'rgba(15,20,30,0.98)',
          border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 6,
          boxShadow: '0 24px 64px rgba(0,0,0,0.7)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          fontFamily: 'monospace',
        }}
      >
        {/* Search row */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '10px 14px',
            borderBottom: '1px solid rgba(255,255,255,0.08)',
            gap: 10,
          }}
        >
          <span style={{ color: '#64748b', fontSize: 14 }}>⌘</span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#e2e8f0',
              fontSize: 14,
              letterSpacing: '0.02em',
            }}
          />
          <span style={{ color: '#475569', fontSize: 10, letterSpacing: '0.08em' }}>ESC to close</span>
        </div>

        {/* Section label */}
        {!query.trim() && history.length > 0 && (
          <div style={{ padding: '6px 14px 2px', color: '#475569', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Recently Used
          </div>
        )}

        {/* Command list */}
        <div ref={listRef} style={{ overflowY: 'auto', flex: 1 }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '24px 14px', color: '#475569', fontSize: 12, textAlign: 'center' }}>
              No commands match &ldquo;{query}&rdquo;
            </div>
          ) : (
            filtered.map((cmd, i) => {
              const isActive = i === activeIdx;
              const isHistoryItem = !query.trim() && history.includes(cmd.id) && i < history.filter((id) => commands.some((c) => c.id === id)).length;
              const showCategoryHeader =
                query.trim() ||
                !isHistoryItem
                  ? i === 0 ||
                    filtered[i - 1]?.category !== cmd.category ||
                    (history.length > 0 && !query.trim() && i === history.filter((id) => commands.some((c) => c.id === id)).length)
                  : false;

              return (
                <React.Fragment key={cmd.id}>
                  {showCategoryHeader && !isHistoryItem && (
                    <div style={{ padding: '8px 14px 2px', color: '#475569', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                      {cmd.category}
                    </div>
                  )}
                  <div
                    onClick={() => execute(cmd)}
                    onMouseEnter={() => setActiveIdx(i)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      padding: '8px 14px',
                      gap: 10,
                      cursor: 'pointer',
                      background: isActive ? 'rgba(59,130,246,0.15)' : 'transparent',
                      borderLeft: isActive ? '2px solid #3b82f6' : '2px solid transparent',
                      transition: 'background 0.1s',
                    }}
                  >
                    {/* Category badge */}
                    <span
                      style={{
                        fontSize: 9,
                        fontWeight: 700,
                        padding: '1px 5px',
                        borderRadius: 2,
                        textTransform: 'uppercase',
                        letterSpacing: '0.08em',
                        color: CATEGORY_COLORS[cmd.category] ?? '#94a3b8',
                        background: `${CATEGORY_COLORS[cmd.category] ?? '#94a3b8'}1a`,
                        border: `1px solid ${CATEGORY_COLORS[cmd.category] ?? '#94a3b8'}33`,
                        flexShrink: 0,
                        minWidth: 44,
                        textAlign: 'center',
                      }}
                    >
                      {cmd.category}
                    </span>

                    {/* Label */}
                    <span style={{ flex: 1, color: '#cbd5e1', fontSize: 13 }}>{cmd.label}</span>

                    {/* Shortcut hint */}
                    {cmd.shortcut && (
                      <kbd
                        style={{
                          background: 'rgba(255,255,255,0.06)',
                          border: '1px solid rgba(255,255,255,0.12)',
                          borderRadius: 3,
                          padding: '1px 6px',
                          color: '#64748b',
                          fontSize: 10,
                          fontFamily: 'monospace',
                        }}
                      >
                        {cmd.shortcut}
                      </kbd>
                    )}

                    {/* History indicator */}
                    {isHistoryItem && (
                      <span style={{ color: '#475569', fontSize: 10 }}>recent</span>
                    )}
                  </div>
                </React.Fragment>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            borderTop: '1px solid rgba(255,255,255,0.06)',
            padding: '6px 14px',
            display: 'flex',
            gap: 16,
            color: '#475569',
            fontSize: 10,
          }}
        >
          <span>↑↓ navigate</span>
          <span>↵ execute</span>
          <span>Autonomy: <span style={{ color: autonomyLevel === 'AUTONOMOUS' ? '#ef4444' : '#94a3b8' }}>{autonomyLevel}</span></span>
          <span style={{ marginLeft: 'auto' }}>{filtered.length} command{filtered.length !== 1 ? 's' : ''}</span>
        </div>
      </div>
    </div>
  );
}
