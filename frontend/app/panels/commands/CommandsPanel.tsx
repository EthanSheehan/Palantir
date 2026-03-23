import { Tag, Intent, NonIdealState, Card } from '@blueprintjs/core';
import { useAppStore } from '../../store/appStore';
import './CommandsPanel.css';

export function CommandsPanel() {
  const commands = useAppStore((s) => s.commands);
  const commandList = Object.values(commands).sort((a, b) =>
    (b.created_at ?? '').localeCompare(a.created_at ?? '')
  );

  if (commandList.length === 0) {
    return (
      <NonIdealState
        icon="console"
        title="Command History"
        description="No commands issued yet."
        className="commands-empty"
      />
    );
  }

  return (
    <div className="commands-panel">
      <h3 className="panel-title">Command History</h3>
      {commandList.map((cmd) => (
        <Card key={cmd.id} interactive className="command-row">
          <span className="command-type">{cmd.type}</span>
          <Tag intent={cmdStateIntent(cmd.state)} minimal className="command-state">
            {cmd.state}
          </Tag>
        </Card>
      ))}
    </div>
  );
}

function cmdStateIntent(state: string): Intent {
  switch (state) {
    case 'completed': return Intent.SUCCESS;
    case 'failed': case 'expired': return Intent.DANGER;
    case 'active': case 'sent': return Intent.PRIMARY;
    case 'approved': case 'validated': return Intent.WARNING;
    default: return Intent.NONE;
  }
}
