import { useState } from 'react';
import { Button, Card, Tag, Intent, InputGroup, HTMLSelect, FormGroup, NonIdealState } from '@blueprintjs/core';
import { useAppStore } from '../../store/appStore';
import { useMissionList } from '../../store/selectors';
import type { Mission } from '../../store/types';
import * as api from '../../services/apiClient';
import './MissionsPanel.css';

const MISSION_TYPES = ['rebalance', 'surveillance', 'delivery', 'patrol', 'emergency_response', 'custom'];
const PRIORITIES = ['low', 'normal', 'high', 'critical'];

export function MissionsPanel() {
  const missions = useMissionList();
  const selectMission = useAppStore((s) => s.selectMission);
  const selectedMissionId = useAppStore((s) => s.selection.missionId);

  const sortedMissions = [...missions].sort((a, b) => {
    const p = { critical: 0, high: 1, normal: 2, low: 3 };
    return (p[a.priority as keyof typeof p] ?? 2) - (p[b.priority as keyof typeof p] ?? 2);
  });

  return (
    <div className="missions-panel">
      <h3 className="panel-title">Missions</h3>

      {sortedMissions.length === 0 ? (
        <NonIdealState
          icon="path"
          description="No missions. Create one below."
          className="missions-empty"
        />
      ) : (
        <div className="mission-list">
          {sortedMissions.map((m) => (
            <MissionCard
              key={m.id}
              mission={m}
              isSelected={m.id === selectedMissionId}
              onSelect={() => selectMission(m.id)}
            />
          ))}
        </div>
      )}

      <CreateMissionForm />
    </div>
  );
}

function MissionCard({
  mission,
  isSelected,
  onSelect,
}: {
  mission: Mission;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const handleAction = async (action: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      switch (action) {
        case 'propose': await api.proposeMission(mission.id); break;
        case 'approve': await api.approveMission(mission.id); break;
        case 'pause': await api.pauseMission(mission.id); break;
        case 'resume': await api.resumeMission(mission.id); break;
        case 'abort': await api.abortMission(mission.id); break;
      }
    } catch (err) {
      console.error(`Mission ${action} failed:`, err);
    }
  };

  return (
    <Card
      className={`mission-card${isSelected ? ' mission-selected' : ''}`}
      interactive
      onClick={onSelect}
    >
      <div className="mission-header">
        <span className="mission-name">{mission.name}</span>
        <Tag intent={stateIntent(mission.state)} minimal>{mission.state}</Tag>
      </div>
      <div className="mission-meta">
        <Tag minimal className="mission-meta-tag">{mission.priority}</Tag>
        <Tag minimal className="mission-meta-tag">{mission.type}</Tag>
      </div>
      <div className="mission-actions">
        {mission.state === 'draft' && (
          <Button small onClick={(e) => handleAction('propose', e)}>Propose</Button>
        )}
        {mission.state === 'proposed' && (
          <Button small intent={Intent.SUCCESS} onClick={(e) => handleAction('approve', e)}>Approve</Button>
        )}
        {mission.state === 'approved' && (
          <Button small onClick={(e) => handleAction('approve', e)}>Queue</Button>
        )}
        {mission.state === 'active' && (
          <Button small intent={Intent.WARNING} onClick={(e) => handleAction('pause', e)}>Pause</Button>
        )}
        {mission.state === 'paused' && (
          <Button small intent={Intent.SUCCESS} onClick={(e) => handleAction('resume', e)}>Resume</Button>
        )}
        {['active', 'paused'].includes(mission.state) && (
          <Button small intent={Intent.DANGER} onClick={(e) => handleAction('abort', e)}>Abort</Button>
        )}
      </div>
    </Card>
  );
}

function CreateMissionForm() {
  const [name, setName] = useState('');
  const [type, setType] = useState('rebalance');
  const [priority, setPriority] = useState('normal');
  const [objective, setObjective] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.createMission({ name, type, priority, objective: objective || undefined });
      setName('');
      setObjective('');
    } catch (err) {
      console.error('Create mission failed:', err);
    }
  };

  return (
    <form className="create-mission-form" onSubmit={handleSubmit}>
      <FormGroup>
        <InputGroup
          placeholder="Mission name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          small
        />
      </FormGroup>
      <div className="form-row">
        <HTMLSelect value={type} onChange={(e) => setType(e.target.value)}>
          {MISSION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </HTMLSelect>
        <HTMLSelect value={priority} onChange={(e) => setPriority(e.target.value)}>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </HTMLSelect>
      </div>
      <InputGroup
        placeholder="Objective (optional)"
        value={objective}
        onChange={(e) => setObjective(e.target.value)}
        small
      />
      <Button type="submit" small fill intent={Intent.PRIMARY} disabled={!name.trim()}>
        Create Mission
      </Button>
    </form>
  );
}

function stateIntent(state: string): Intent {
  switch (state) {
    case 'active': return Intent.SUCCESS;
    case 'completed': return Intent.PRIMARY;
    case 'failed': case 'aborted': return Intent.DANGER;
    case 'paused': return Intent.WARNING;
    case 'approved': return Intent.SUCCESS;
    case 'proposed': return Intent.WARNING;
    default: return Intent.NONE;
  }
}
