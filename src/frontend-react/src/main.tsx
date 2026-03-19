import React from 'react';
import ReactDOM from 'react-dom/client';
import '@blueprintjs/core/lib/css/blueprint.css';
import '@blueprintjs/icons/lib/css/blueprint-icons.css';
import { FocusStyleManager } from '@blueprintjs/core';
import App from './App';

FocusStyleManager.onlyShowFocusOnTabs();

ReactDOM.createRoot(document.getElementById('root')!).render(<App />);
