import { useState, useCallback, useEffect, useRef } from 'react';

export function useResizable(initialWidth = 300, minWidth = 280, maxWidth = 800) {
  const [width, setWidth] = useState(initialWidth);
  const isResizingRef = useRef(false);
  const onResizeRef = useRef<(() => void) | null>(null);

  const setOnResize = useCallback((fn: () => void) => {
    onResizeRef.current = fn;
  }, []);

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      if (!isResizingRef.current) return;
      let newWidth = e.clientX;
      if (newWidth < minWidth) newWidth = minWidth;
      if (newWidth > maxWidth) newWidth = maxWidth;
      setWidth(newWidth);
      onResizeRef.current?.();
    }

    function onMouseUp() {
      if (isResizingRef.current) {
        isResizingRef.current = false;
        document.body.style.cursor = '';
      }
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, [minWidth, maxWidth]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    isResizingRef.current = true;
    document.body.style.cursor = 'col-resize';
    e.preventDefault();
  }, []);

  return { width, onMouseDown, setOnResize };
}
