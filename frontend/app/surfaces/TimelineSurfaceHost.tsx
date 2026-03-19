import { useEffect, useRef } from 'react';

/**
 * Hosts the existing timeline canvas panel by reparenting #timelinePanel.
 * Uses ResizeObserver to keep the canvas sized correctly.
 */
export function TimelineSurfaceHost() {
  const containerRef = useRef<HTMLDivElement>(null);
  const adoptedRef = useRef(false);

  useEffect(() => {
    if (adoptedRef.current) return;

    const timelineEl = document.getElementById('timelinePanel');
    if (timelineEl && containerRef.current) {
      containerRef.current.appendChild(timelineEl);
      adoptedRef.current = true;

      // Resize timeline canvas after reparenting
      const TimelinePanel = (window as any).TimelinePanel;
      if (TimelinePanel?.resize) {
        requestAnimationFrame(() => TimelinePanel.resize());
      }
    }

    // ResizeObserver to keep timeline canvas sized
    const observer = new ResizeObserver(() => {
      const TimelinePanel = (window as any).TimelinePanel;
      if (TimelinePanel?.resize) {
        TimelinePanel.resize();
      }
    });

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => {
      observer.disconnect();
      if (adoptedRef.current) {
        const timelineEl = document.getElementById('timelinePanel');
        if (timelineEl) {
          document.body.appendChild(timelineEl);
          adoptedRef.current = false;
        }
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="timeline-surface-host"
      style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
    />
  );
}
