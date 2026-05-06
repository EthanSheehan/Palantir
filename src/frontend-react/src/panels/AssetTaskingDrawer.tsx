import React, { useEffect, useState } from 'react';
import { Button, Intent, Icon, IconName, Tag, ProgressBar } from '@blueprintjs/core';
import { useSimStore } from '../store/SimulationStore';
import { useSendMessage } from '../App';

/**
 * AssetTaskingDrawer — surface for the AI Asset Tasking Recommender.
 *
 * Triggered by selecting a target. Sends `request_tasking_recommendations`
 * over the WebSocket; the backend `ai_tasking_manager.evaluate_and_retask_async`
 * returns a ranked list of `SensorTaskingOrder`. Each order renders as a card
 * with the why-trace, distance/ETA, sensor fit. One-click Task fires the
 * existing `retask_sensors` action for that asset.
 */

interface TaskingOrder {
  order_id: string;
  asset_id: string;
  target_detection_id: string;
  collection_type: string;
  priority: number;
  estimated_collection_time_minutes: number;
  reasoning: string;
}

const COLLECTION_COLORS: Record<string, string> = {
  'EO/IR':  '#4A90E2',
  SAR:      '#7ED321',
  SIGINT:   '#F5A623',
  FMV:      '#a855f7',
  GMTI:     '#06b6d4',
};

interface Props { visible: boolean; onClose: () => void; }

export function AssetTaskingDrawer({ visible, onClose }: Props) {
  const sendMessage = useSendMessage();
  const targets = useSimStore(s => s.targets);
  const selectedId = useSimStore(s => s.selectedTargetId);
  const [orders, setOrders] = useState<TaskingOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const target = targets.find(t => t.id === selectedId);

  useEffect(() => {
    if (!visible || !target) {
      setOrders([]);
      return;
    }
    setLoading(true);
    sendMessage({ action: 'request_tasking_recommendations', target_id: target.id });
    function onResponse(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail && detail.target_id === target?.id) {
        setOrders(detail.tasking_orders ?? []);
        setLoading(false);
      }
    }
    window.addEventListener('grid-sentinel:tasking-response', onResponse);
    const fallback = setTimeout(() => setLoading(false), 4000);
    return () => {
      window.removeEventListener('grid-sentinel:tasking-response', onResponse);
      clearTimeout(fallback);
    };
  }, [visible, target?.id, sendMessage]);

  if (!visible) return null;
  if (!target) {
    return (
      <DrawerShell title="ASSET TASKING" onClose={onClose}>
        <div style={{ padding: 16, color: '#64748b', fontSize: 11, fontStyle: 'italic' }}>
          Select a target to request tasking recommendations.
        </div>
      </DrawerShell>
    );
  }

  return (
    <DrawerShell title={`ASSET TASKING · TGT #${String(target.id).padStart(4, '0')}`} onClose={onClose}>
      <div style={{
        padding: '6px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(15, 20, 30, 0.95)',
        fontSize: 10,
        color: '#94a3b8',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Type: <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{target.type}</span></span>
          <span>State: <span style={{ color: '#e2e8f0' }}>{target.state}</span></span>
          <span>Conf: <span style={{ color: '#e2e8f0' }}>{Math.round((target.fused_confidence ?? 0) * 100)}%</span></span>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: 16 }}>
          <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 6 }}>Querying recommender …</div>
          <ProgressBar intent={Intent.PRIMARY} />
        </div>
      ) : orders.length === 0 ? (
        <div style={{ padding: 16, color: '#64748b', fontSize: 11, fontStyle: 'italic' }}>
          No assets currently available for retasking on this target.
        </div>
      ) : (
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {orders.map((o, idx) => (
            <OrderCard
              key={o.order_id}
              order={o}
              rank={idx + 1}
              onTask={() =>
                sendMessage({
                  action: 'retask_sensors',
                  order_id: o.order_id,
                  asset_id: o.asset_id,
                  target_id: target.id,
                  collection_type: o.collection_type,
                })
              }
            />
          ))}
        </div>
      )}
    </DrawerShell>
  );
}

function OrderCard({ order, rank, onTask }: { order: TaskingOrder; rank: number; onTask: () => void }) {
  const color = COLLECTION_COLORS[order.collection_type] ?? '#94a3b8';
  return (
    <div style={{
      padding: '8px 10px',
      borderBottom: '1px solid rgba(255,255,255,0.05)',
      borderLeft: `3px solid ${color}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontFamily: 'monospace', fontSize: 9, color: '#475569' }}>#{rank}</span>
          <span style={{ fontWeight: 700, fontSize: 11, color: '#e2e8f0' }}>{order.asset_id}</span>
          <Tag minimal style={{ background: `${color}22`, color, border: `1px solid ${color}55`, fontSize: 9, padding: '0 4px', minHeight: 14 }}>
            {order.collection_type}
          </Tag>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <span key={i} style={{
              width: 5, height: 8,
              background: i < order.priority ? '#22c55e' : 'rgba(255,255,255,0.08)',
              borderRadius: 1,
            }} />
          ))}
          <span style={{ fontSize: 9, color: '#94a3b8', marginLeft: 4 }}>P{order.priority}</span>
        </div>
      </div>
      <div style={{ fontSize: 10, color: '#cbd5e1', marginBottom: 4 }}>
        ETA: <span style={{ color: '#22d3ee' }}>{order.estimated_collection_time_minutes.toFixed(1)}m</span>
      </div>
      <div style={{
        fontSize: 10,
        color: '#94a3b8',
        fontStyle: 'italic',
        background: 'rgba(255,255,255,0.03)',
        borderRadius: 2,
        padding: '4px 6px',
        marginBottom: 6,
        lineHeight: 1.4,
      }}>
        <Icon icon={'lightbulb' as IconName} size={10} style={{ marginRight: 4 }} />
        {order.reasoning}
      </div>
      <Button
        small intent={Intent.PRIMARY}
        text="TASK"
        icon={'send-to' as IconName}
        style={{ fontSize: 10 }}
        onClick={onTask}
      />
    </div>
  );
}

function DrawerShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div style={{
      position: 'fixed',
      top: 80,
      right: 12,
      width: 340,
      maxHeight: 'calc(100vh - 100px)',
      background: 'rgba(7, 11, 17, 0.97)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: 4,
      boxShadow: '-8px 8px 32px rgba(0,0,0,0.55)',
      zIndex: 8200,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        background: 'rgba(15, 20, 30, 0.95)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon icon={'send-to-graph' as IconName} size={12} color="#22d3ee" />
          <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 11, letterSpacing: '0.16em', color: '#e2e8f0' }}>
            {title}
          </span>
        </div>
        <Button minimal small icon={'cross' as IconName} onClick={onClose} aria-label="Close drawer" />
      </div>
      {children}
    </div>
  );
}
