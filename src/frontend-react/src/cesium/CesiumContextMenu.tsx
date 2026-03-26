import React, { useEffect, useRef } from 'react';
import { Menu, MenuItem, MenuDivider } from '@blueprintjs/core';
import { useSendMessage } from '../App';

interface ContextMenuPosition {
  x: number;
  y: number;
}

interface CesiumContextMenuProps {
  position: ContextMenuPosition;
  entityType: 'drone' | 'target' | null;
  entityId: string | null;
  onClose: () => void;
}

export function CesiumContextMenu({ position, entityType, entityId, onClose }: CesiumContextMenuProps) {
  const sendMessage = useSendMessage();
  const menuRef = useRef<HTMLDivElement>(null);

  // Parse numeric ID from entity string (e.g. "target_3" -> 3, "uav_1" -> 1)
  const numericId = entityId
    ? parseInt(entityId.replace(/^(target_|uav_)/, ''), 10)
    : null;

  // Close on click outside or Escape key
  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  // Clamp menu position so it stays within viewport
  const menuStyle: React.CSSProperties = {
    position: 'fixed',
    left: Math.min(position.x, window.innerWidth - 180),
    top: Math.min(position.y, window.innerHeight - 200),
    zIndex: 9999,
    minWidth: 160,
    boxShadow: '0 4px 20px rgba(0,0,0,0.6)',
    background: '#1c2127',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 3,
  };

  if (entityType === 'target' && numericId !== null) {
    return (
      <div ref={menuRef} style={menuStyle}>
        <Menu>
          <MenuItem
            icon="locate"
            text="Follow"
            onClick={() => {
              sendMessage({ action: 'scan_area', target_id: numericId });
              onClose();
            }}
          />
          <MenuItem
            icon="eye-open"
            text="Paint"
            onClick={() => {
              sendMessage({ action: 'paint_target', target_id: numericId });
              onClose();
            }}
          />
          <MenuItem
            icon="endorsed"
            text="Verify"
            onClick={() => {
              sendMessage({ action: 'verify_target', target_id: numericId });
              onClose();
            }}
          />
          <MenuDivider />
          <MenuItem
            icon="flag"
            text="Nominate"
            intent="warning"
            onClick={() => {
              if (!window.confirm(`Confirm nomination for target ${numericId}?`)) return;
              sendMessage({ action: 'approve_nomination', target_id: numericId });
              onClose();
            }}
          />
        </Menu>
      </div>
    );
  }

  if (entityType === 'drone' && numericId !== null) {
    return (
      <div ref={menuRef} style={menuStyle}>
        <Menu>
          <MenuItem
            icon="search"
            text="Set SEARCH"
            onClick={() => {
              sendMessage({ action: 'scan_area', drone_id: numericId });
              onClose();
            }}
          />
          <MenuItem
            icon="send-to"
            text="Assign Target"
            onClick={() => {
              // Open target assignment by selecting the drone — user picks target from sidebar
              window.dispatchEvent(new CustomEvent('palantir:assignTarget', { detail: { droneId: numericId } }));
              onClose();
            }}
          />
          <MenuDivider />
          <MenuItem
            icon="home"
            text="RTB"
            intent="danger"
            onClick={() => {
              sendMessage({ action: 'move_drone', drone_id: numericId, rtb: true });
              onClose();
            }}
          />
        </Menu>
      </div>
    );
  }

  return null;
}
