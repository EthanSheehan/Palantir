import { state } from './state.js';

export const TARGET_MAP = {
    'SAM':       { color: '#ff4444', label: 'SAM' },
    'TEL':       { color: '#ffa500', label: 'TEL' },
    'TRUCK':     { color: '#eab308', label: 'TRK' },
    'CP':        { color: '#a855f7', label: 'CP' },
    'MANPADS':   { color: '#ec4899', label: 'MAN' },
    'RADAR':     { color: '#06b6d4', label: 'RDR' },
    'ARTILLERY': { color: '#92400e', label: 'ART' },
    'APC':       { color: '#94a3b8', label: 'APC' },
    'C2_NODE':   { color: '#06b6d4', label: 'C2' },
    'LOGISTICS': { color: '#94a3b8', label: 'LOG' }
};

const THREAT_RING_TYPES = new Set(['SAM', 'MANPADS']);
const THREAT_RING_RADIUS = 5000; // 5km

const targetEntities = {};
const threatRingEntities = {};
const targetSvgCache = {};

// Expose for lock indicators in drones.js
window._targetEntities = targetEntities;

export function getTargetEntities() {
    return targetEntities;
}

export function getTargetIcon(target) {
    const config = TARGET_MAP[target.type] || { color: '#ffcc00', label: 'TGT' };
    const confidence = target.detection_confidence || (target.detected ? 1.0 : 0.3);
    const targetState = target.state || (target.detected ? 'DETECTED' : 'UNDETECTED');
    const isVisible = targetState !== 'UNDETECTED';
    const isNeutralized = targetState === 'NEUTRALIZED';
    const isConcealed = target.concealed === true;

    const color = isNeutralized ? '#4a5568' : (isVisible ? config.color : 'rgba(255, 204, 0, 0.5)');
    const size = isVisible ? 32 : 20;
    const opacity = isConcealed ? 0.4 : confidence;

    const cacheKey = `${target.type}_${targetState}_${Math.round(confidence * 10)}_${isConcealed ? 'c' : 'v'}`;
    if (targetSvgCache[cacheKey]) return targetSvgCache[cacheKey];

    // Neutralized targets get a crossed-out style
    const crossLine = isNeutralized
        ? `<line x1="4" y1="4" x2="${size - 4}" y2="${size - 4}" stroke="#ef4444" stroke-width="2" opacity="0.7"/>
           <line x1="${size - 4}" y1="4" x2="4" y2="${size - 4}" stroke="#ef4444" stroke-width="2" opacity="0.7"/>`
        : '';

    const svg = `<svg width="${size}" height="${size + 14}" viewBox="0 0 ${size} ${size + 14}" xmlns="http://www.w3.org/2000/svg">
        <circle cx="${size/2}" cy="${size/2}" r="${size/2 - 2}" stroke="${color}" stroke-width="2" fill="none" opacity="${opacity}" />
        <circle cx="${size/2}" cy="${size/2}" r="${size/4}" fill="${color}" opacity="${opacity}" />
        ${crossLine}
        ${isVisible ? `<text x="${size/2}" y="${size + 12}" fill="${color}" font-size="10" font-family="Inter" font-weight="bold" text-anchor="middle" opacity="${opacity}">${config.label}</text>` : ''}
    </svg>`;
    const url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    targetSvgCache[cacheKey] = url;
    return url;
}

export function updateTargets(targets) {
    const viewer = state.viewer;
    const currentTargetIds = new Set();

    targets.forEach(t => {
        currentTargetIds.add(t.id);
        const position = Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0);
        const confidence = t.detection_confidence || (t.detected ? 1.0 : 0.3);
        const targetState = t.state || (t.detected ? 'DETECTED' : 'UNDETECTED');
        const isConcealed = t.concealed === true;
        const billboardAlpha = isConcealed ? 0.35 : Math.max(0.3, confidence);

        if (!targetEntities[t.id]) {
            const positionProperty = new Cesium.SampledPositionProperty();
            positionProperty.forwardExtrapolationType = Cesium.ExtrapolationType.HOLD;
            positionProperty.setInterpolationOptions({
                interpolationDegree: 2,
                interpolationAlgorithm: Cesium.HermitePolynomialApproximation
            });
            positionProperty.addSample(viewer.clock.currentTime, position);

            const marker = viewer.entities.add({
                id: `target_${t.id}`,
                name: `Target-${t.id}`,
                position: positionProperty,
                billboard: {
                    image: getTargetIcon(t),
                    verticalOrigin: Cesium.VerticalOrigin.CENTER,
                    heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
                    color: Cesium.Color.WHITE.withAlpha(billboardAlpha)
                }
            });
            targetEntities[t.id] = marker;

            // Add click handler via screenSpaceEventHandler (handled in mapclicks or app.js)
        } else {
            const marker = targetEntities[t.id];
            let targetTime;
            if (!marker._lastTargetTime) {
                targetTime = Cesium.JulianDate.addSeconds(viewer.clock.currentTime, 0.3, new Cesium.JulianDate());
            } else {
                targetTime = Cesium.JulianDate.addSeconds(marker._lastTargetTime, 0.1, new Cesium.JulianDate());
            }
            marker._lastTargetTime = targetTime;
            marker.position.addSample(targetTime, position);
            marker.billboard.image = getTargetIcon(t);
            marker.billboard.color = Cesium.Color.WHITE.withAlpha(billboardAlpha);
        }

        // Threat rings for SAM/MANPADS
        if (THREAT_RING_TYPES.has(t.type) && targetState !== 'UNDETECTED' && targetState !== 'NEUTRALIZED') {
            if (!threatRingEntities[t.id]) {
                const config = TARGET_MAP[t.type] || { color: '#ff4444' };
                const cesiumColor = Cesium.Color.fromCssColorString(config.color).withAlpha(0.3);
                const ring = viewer.entities.add({
                    id: `threat_ring_${t.id}`,
                    position: Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0),
                    ellipse: {
                        semiMajorAxis: THREAT_RING_RADIUS,
                        semiMinorAxis: THREAT_RING_RADIUS,
                        fill: true,
                        material: cesiumColor,
                        outline: true,
                        outlineColor: Cesium.Color.fromCssColorString(config.color).withAlpha(0.6),
                        outlineWidth: 2,
                        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
                    }
                });
                threatRingEntities[t.id] = ring;
            } else {
                threatRingEntities[t.id].position = Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0);
            }
        } else if (threatRingEntities[t.id]) {
            viewer.entities.remove(threatRingEntities[t.id]);
            delete threatRingEntities[t.id];
        }
    });

    // Cleanup removed targets
    Object.keys(targetEntities).forEach(id => {
        if (!currentTargetIds.has(parseInt(id))) {
            viewer.entities.remove(targetEntities[id]);
            delete targetEntities[id];
            if (threatRingEntities[id]) {
                viewer.entities.remove(threatRingEntities[id]);
                delete threatRingEntities[id];
            }
        }
    });
}

