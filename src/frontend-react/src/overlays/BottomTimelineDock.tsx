import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Button, Slider, Intent, Tag, Icon } from '@blueprintjs/core';

interface TimelineRange {
  start: number | null;
  end: number | null;
  count: number;
}

interface Props {
  visible: boolean;
  onToggle: () => void;
}

export function BottomTimelineDock({ visible, onToggle }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [range, setRange] = useState<TimelineRange>({ start: null, end: null, count: 0 });
  const [scrubTime, setScrubTime] = useState<number | null>(null);
  const [isLive, setIsLive] = useState(true);
  const [playing, setPlaying] = useState(false);
  const playIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!visible) return;
    function fetchRange() {
      fetch('/api/history/range')
        .then(r => r.json())
        .then(setRange)
        .catch(() => {});
    }
    fetchRange();
    const id = setInterval(fetchRange, 10000);
    return () => clearInterval(id);
  }, [visible]);

  const returnToLive = useCallback(() => {
    setIsLive(true);
    setScrubTime(null);
    setPlaying(false);
    if (playIntervalRef.current) clearInterval(playIntervalRef.current);
  }, []);

  const onScrub = useCallback((value: number) => {
    setScrubTime(value);
    setIsLive(false);
  }, []);

  const togglePlayback = useCallback(() => {
    if (!scrubTime || !range.end) return;
    if (playing) {
      setPlaying(false);
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    } else {
      setPlaying(true);
      playIntervalRef.current = setInterval(() => {
        setScrubTime(prev => {
          if (prev === null || !range.end) return prev;
          const next = prev + 5;
          if (next >= range.end) {
            setPlaying(false);
            if (playIntervalRef.current) clearInterval(playIntervalRef.current);
            return range.end;
          }
          return next;
        });
      }, 1000);
    }
  }, [playing, scrubTime, range.end]);

  useEffect(() => {
    return () => {
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    };
  }, []);

  useEffect(() => {
    if (isLive || scrubTime === null) return;
    fetch(`/api/history/state?at=${scrubTime}`)
      .then(r => r.json())
      .then(data => {
        if (data.state) {
          window.dispatchEvent(new CustomEvent('palantir:historicalState', { detail: data.state }));
        }
      })
      .catch(() => {});
  }, [scrubTime, isLive]);

  if (!visible) return null;

  const formatTime = (ts: number) => new Date(ts * 1000).toLocaleTimeString();

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 300,
      right: 0,
      height: expanded ? 120 : 40,
      background: 'rgba(15, 20, 30, 0.95)',
      borderTop: '1px solid rgba(100, 180, 255, 0.3)',
      zIndex: 8000,
      display: 'flex',
      flexDirection: 'column',
      transition: 'height 0.2s ease',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: '0 12px', height: 40, gap: 8 }}>
        <Button small minimal icon={expanded ? 'chevron-down' : 'chevron-up'} onClick={() => setExpanded(v => !v)} />
        <Icon icon="timeline-events" size={14} style={{ color: 'rgba(100,180,255,0.8)' }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.8)' }}>TIMELINE</span>

        {isLive ? (
          <Tag intent={Intent.SUCCESS} minimal style={{ fontSize: 10 }}>LIVE</Tag>
        ) : (
          <>
            <Tag intent={Intent.WARNING} minimal style={{ fontSize: 10 }}>
              {scrubTime ? formatTime(scrubTime) : 'HISTORICAL'}
            </Tag>
            <Button small minimal intent={Intent.PRIMARY} onClick={returnToLive} icon="redo">
              RETURN TO LIVE
            </Button>
          </>
        )}

        <div style={{ flex: 1 }} />
        {range.count > 0 && (
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>
            {range.count} snapshots
          </span>
        )}
        <Button small minimal icon="cross" onClick={onToggle} />
      </div>

      {expanded && range.start && range.end && (
        <div style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button
            small
            icon={playing ? 'pause' : 'play'}
            intent={Intent.PRIMARY}
            onClick={togglePlayback}
            disabled={isLive}
          />
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', width: 70 }}>
            {formatTime(range.start)}
          </span>
          <div style={{ flex: 1 }}>
            <Slider
              min={range.start}
              max={range.end}
              value={scrubTime ?? range.end}
              onChange={onScrub}
              stepSize={5}
              labelRenderer={false}
            />
          </div>
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', width: 70, textAlign: 'right' }}>
            {formatTime(range.end)}
          </span>
        </div>
      )}
    </div>
  );
}
