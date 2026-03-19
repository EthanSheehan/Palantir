import { useCallback, useEffect, useRef, useState } from 'react';
import { TimelineSurfaceHost } from '../surfaces/TimelineSurfaceHost';
import { useAppStore } from '../store/appStore';

/**
 * Floating timeline pill (clock) + expandable drawer with timeline canvas.
 */
export function BottomTimelineDock() {
  const layout = useAppStore((s) => s.ui.layout);
  const setLayout = useAppStore((s) => s.setLayout);

  const [expanded, setExpanded] = useState(layout.timelineExpanded);
  const [height, setHeight] = useState(layout.timelineHeight); // vh
  const [isDragging, setIsDragging] = useState(false);
  const [clock, setClock] = useState(formatClock());
  const drawerRef = useRef<HTMLDivElement>(null);
  const dragState = useRef({ startY: 0, startH: 0 });

  // Clock update
  useEffect(() => {
    const interval = setInterval(() => setClock(formatClock()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Toggle drawer
  const toggle = useCallback(() => {
    const next = !expanded;
    setExpanded(next);
    setLayout({ timelineExpanded: next });
  }, [expanded, setLayout]);

  // Compute pill position
  const pillBottom = expanded
    ? 8 + (window.innerHeight * height) / 100 + 8
    : 16;

  // Resize drag
  const onResizeMouseDown = useCallback((e: React.MouseEvent) => {
    if (!expanded) return;
    e.preventDefault();
    e.stopPropagation();
    const rect = drawerRef.current?.getBoundingClientRect();
    dragState.current = { startY: e.clientY, startH: rect?.height ?? 200 };
    setIsDragging(true);
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
  }, [expanded]);

  useEffect(() => {
    if (!isDragging) return;

    function onMouseMove(e: MouseEvent) {
      const delta = dragState.current.startY - e.clientY;
      const newH = dragState.current.startH + delta;
      const vh = window.innerHeight;
      const pct = Math.max(15, Math.min(80, (newH / vh) * 100));
      setHeight(pct);
    }

    function onMouseUp() {
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      setLayout({ timelineHeight: height });
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, [isDragging, height, setLayout]);

  // Sync from store on mount
  useEffect(() => {
    if (layout.timelineExpanded && !expanded) {
      setExpanded(true);
    }
  }, [layout.timelineExpanded]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {/* Pill */}
      <div
        className="ws-timeline-pill"
        style={{ bottom: pillBottom }}
        onClick={toggle}
      >
        <span className="ws-date-day">{clock.day}</span>
        <span className="ws-date-month">{clock.month}</span>
        <span className="ws-date-year">{clock.year}</span>
        <span className="ws-date-sep">|</span>
        <span className="ws-date-time">{clock.time}</span>
      </div>

      {/* Drawer */}
      <div
        ref={drawerRef}
        className={`ws-timeline-drawer${expanded ? ' ws-open' : ''}${isDragging ? ' ws-dragging' : ''}`}
        style={expanded ? { height: height + 'vh' } : undefined}
      >
        <div
          className="ws-timeline-resize-handle"
          onMouseDown={onResizeMouseDown}
        />
        <div className="ws-timeline-drawer-header" />
        <TimelineSurfaceHost />
      </div>
    </>
  );
}

function formatClock() {
  const now = new Date();
  return {
    day: String(now.getDate()),
    month: now.toLocaleString('en-US', { month: 'long' }).toUpperCase(),
    year: String(now.getFullYear()),
    time: [
      String(now.getHours()).padStart(2, '0'),
      String(now.getMinutes()).padStart(2, '0'),
      String(now.getSeconds()).padStart(2, '0'),
    ].join(':'),
  };
}
