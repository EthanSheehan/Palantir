/**
 * LayoutPersistence — Save/restore workspace layout state to localStorage.
 * Debounced writes, schema versioning, validation.
 */
const LayoutPersistence = (() => {
    const STORAGE_KEY = 'ams.workspace.layout';
    const CURRENT_VERSION = 1;

    let _saveTimer = null;
    const DEBOUNCE_MS = 500;

    const DEFAULT_LAYOUT_STATE = {
        version: CURRENT_VERSION,
        regions: {
            left: { width: 380, collapsed: false, activeTab: 'missions' },
            right: { width: 340, visible: false },
            bottom: { height: 240, collapsed: false, activeTab: 'timeline' },
        },
    };

    function save(state) {
        if (_saveTimer) clearTimeout(_saveTimer);
        _saveTimer = setTimeout(() => {
            try {
                const toSave = Object.assign({}, state, { version: CURRENT_VERSION });
                localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
            } catch (e) {
                console.warn('LayoutPersistence: failed to save', e);
            }
        }, DEBOUNCE_MS);
    }

    function load() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return DEFAULT_LAYOUT_STATE;

            const state = JSON.parse(raw);
            return _validate(_migrate(state));
        } catch (e) {
            console.warn('LayoutPersistence: failed to load, using defaults', e);
            return DEFAULT_LAYOUT_STATE;
        }
    }

    function _migrate(state) {
        if (!state || !state.version) {
            return DEFAULT_LAYOUT_STATE;
        }
        // Version 1 is current — no migration needed
        if (state.version === 1) {
            return state;
        }
        // Unknown version — reset
        return DEFAULT_LAYOUT_STATE;
    }

    function _validate(state) {
        if (!state.regions) return DEFAULT_LAYOUT_STATE;
        const r = state.regions;

        // Clamp sizes
        if (r.left) {
            r.left.width = Math.max(240, Math.min(800, r.left.width || 380));
        }
        if (r.right) {
            r.right.width = Math.max(240, Math.min(600, r.right.width || 340));
        }
        if (r.bottom) {
            r.bottom.height = Math.max(120, Math.min(600, r.bottom.height || 240));
        }

        return state;
    }

    function reset() {
        localStorage.removeItem(STORAGE_KEY);
        return DEFAULT_LAYOUT_STATE;
    }

    function getDefault() {
        return JSON.parse(JSON.stringify(DEFAULT_LAYOUT_STATE));
    }

    return {
        save,
        load,
        reset,
        getDefault,
        STORAGE_KEY,
    };
})();
