import React from 'react';
import { Button, ButtonGroup, Intent } from '@blueprintjs/core';
import type { CamLayout } from '../store/types';

interface CamLayoutSelectorProps {
  layout: CamLayout;
  onLayoutChange: (layout: CamLayout) => void;
}

const LAYOUTS: { key: CamLayout; label: string }[] = [
  { key: 'SINGLE', label: '1' },
  { key: 'PIP', label: 'PIP' },
  { key: 'SPLIT', label: '2' },
  { key: 'QUAD', label: '4' },
];

export function CamLayoutSelector({ layout, onLayoutChange }: CamLayoutSelectorProps) {
  return (
    <ButtonGroup>
      {LAYOUTS.map(l => (
        <Button
          key={l.key}
          active={layout === l.key}
          intent={layout === l.key ? Intent.PRIMARY : Intent.NONE}
          onClick={() => onLayoutChange(l.key)}
          text={l.label}
          style={{ fontFamily: 'monospace', fontSize: 11 }}
        />
      ))}
    </ButtonGroup>
  );
}
