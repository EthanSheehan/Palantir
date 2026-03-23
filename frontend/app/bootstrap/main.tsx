import { createRoot } from 'react-dom/client';
import { App } from './App';
import { initLegacyBridge } from '../store/adapters/legacyAppStateBridge';

// Import Blueprint CSS + global overrides
import '@blueprintjs/core/lib/css/blueprint.css';
import '@blueprintjs/icons/lib/css/blueprint-icons.css';
import '@blueprintjs/select/lib/css/blueprint-select.css';
import '../theme/global-overrides.css';

// Initialize the legacy AppState ↔ Zustand bridge
initLegacyBridge();

// Mount React root — runs after legacy IIFE scripts have loaded
const reactRoot = document.createElement('div');
reactRoot.id = 'react-root';
document.body.appendChild(reactRoot);

const root = createRoot(reactRoot);
root.render(<App />);

console.log('[React] Root mounted');
