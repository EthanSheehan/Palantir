/**
 * PaneRegistry — Central declaration of every pane available in the workspace.
 * Decouples pane content from pane placement.
 */
const PaneRegistry = (() => {
    const _panes = {};       // id → PaneDefinition
    const _components = {};  // id → MountablePane adapter

    function register(definition) {
        _panes[definition.id] = definition;
    }

    function registerComponent(paneId, component) {
        _components[paneId] = component;
    }

    function get(paneId) {
        return _panes[paneId] || null;
    }

    function getAll() {
        return Object.values(_panes);
    }

    function getForRegion(regionId) {
        return Object.values(_panes).filter(p =>
            p.allowedRegions.includes(regionId)
        );
    }

    function getComponent(paneId) {
        return _components[paneId] || null;
    }

    return {
        register,
        registerComponent,
        get,
        getAll,
        getForRegion,
        getComponent,
    };
})();
