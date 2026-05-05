import React, { useEffect, useRef } from 'react';
import { Menu, MenuItem, MenuDivider } from '@blueprintjs/core';
import { useSendMessage } from '../App';
import { useSimStore } from '../store/SimulationStore';

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
              const droneId = useSimStore.getState().trackedDroneId ?? useSimStore.getState().selectedDroneId;
              if (droneId === null) {
                console.warn('CesiumContextMenu Follow: no drone selected');
                return;
              }
              sendMessage({ action: 'follow_target', drone_id: droneId, target_id: numericId });
              onClose();
            }}
          />
          <MenuItem
            icon="eye-open"
            text="Paint"
            onClick={() => {
              const droneId = useSimStore.getState().trackedDroneId ?? useSimStore.getState().selectedDroneId;
              if (droneId === null) {
                console.warn('CesiumContextMenu Paint: no drone selected');
                return;
              }
              sendMessage({ action: 'paint_target', drone_id: droneId, target_id: numericId });
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
            text="Review Nomination"
            intent="warning"
            onClick={() => {
              useSimStore.getState().setActiveTab('mission');
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
              window.dispatchEvent(new CustomEvent('grid-sentinel:assignTarget', { detail: { droneId: numericId } }));
              onClose();
            }}
          />
          <MenuDivider />
          <MenuItem
            icon="home"
            text="RTB"
            intent="danger"
            onClick={() => {
              const theater = useSimStore.getState().theater;
              if (!theater) {
                console.warn('CesiumContextMenu RTB: no theater loaded');
                return;
              }
              const { bounds } = theater;
              const baseLon = (bounds.min_lon + bounds.max_lon) / 2;
              const baseLat = bounds.min_lat + (bounds.max_lat - bounds.min_lat) * 0.1;
              sendMessage({ action: 'move_drone', drone_id: numericId, target_lon: baseLon, target_lat: baseLat });
              onClose();
            }}
          />
        </Menu>
      </div>
    );
  }

  return null;
}
