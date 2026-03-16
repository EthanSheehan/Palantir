/**
 * CesiumManager - Ported from Grid 9 for Palantir
 * Handles 3D Geospatial Visualization and Drone Tracking
 */

class CesiumManager {
    constructor(containerId) {
        Cesium.Ion.defaultAccessToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJmNTg1MmY5OC05NWQ0LTQ0MDEtYTFmMy0yMWI0YzEwYzRiNjciLCJpZCI6NDAzNzE1LCJpYXQiOjE3NzM1MTczMjV9.pfteEFlBPi85hAolMWsVyZkuRTwSeg_-bF5dlTMcWHo';
        
        this.viewer = new Cesium.Viewer(containerId, {
            terrain: Cesium.Terrain.fromWorldTerrain(),
            animation: false,
            baseLayerPicker: false,
            fullscreenButton: false,
            geocoder: false,
            homeButton: false,
            infoBox: false,
            sceneModePicker: false,
            selectionIndicator: false,
            timeline: false,
            navigationHelpButton: false,
            navigationInstructionsInitiallyVisible: false
        });

        // Use Dark Mode Tiles
        this.viewer.imageryLayers.removeAll();
        this.viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
            url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}.png?api_key=74c21d3f-b418-4db6-9318-ffb876f1f071'
        }));

        this.viewer.scene.globe.baseColor = Cesium.Color.BLACK;
        this.viewer.scene.backgroundColor = Cesium.Color.BLACK;
        this.viewer.scene.globe.enableLighting = true;
        this.viewer.scene.globe.depthTestAgainstTerrain = true;
        
        // Initial AO View (Kurdistan)
        this.viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(44.3615, 33.3128, 10000.0),
            orientation: {
                heading: Cesium.Math.toRadians(0),
                pitch: Cesium.Math.toRadians(-45.0),
                roll: 0.0
            },
            duration: 0
        });

        this.entities = {}; // Track all entities locally
        this.isPOVActive = false;
        this.trackedDroneId = null;
    }

    updateTracks(tracks) {
        tracks.forEach(track => {
            const trackId = track.track_id || track.id;
            const type = track.type || track.classification;
            const lon = track.kinematics.longitude;
            const lat = track.kinematics.latitude;
            const alt = track.metadata ? track.metadata.altitude || 0 : 0;
            const yaw = track.metadata ? track.metadata.yaw || 0 : 0;
            const affiliation = track.metadata ? track.metadata.affiliation : 'UNKNOWN';
            const isLocked = track.kill_chain_state === 'LOCK';

            let entity = this.entities[trackId];
            const position = Cesium.Cartesian3.fromDegrees(lon, lat, type === 'UAV' ? alt : 0);

            if (!entity) {
                entity = this.createTacticalEntity(trackId, type, affiliation, position);
                this.entities[trackId] = entity;
            } else {
                entity.position = position;
                if (type === 'UAV') {
                    // Correct Heading: sim yaw is 0=N, 90=E (Clockwise).
                    // Cesium HPR heading is also clockwise from North.
                    const hpr = new Cesium.HeadingPitchRoll(Cesium.Math.toRadians(yaw), 0, 0);
                    entity.orientation = Cesium.Transforms.headingPitchRollQuaternion(position, hpr);
                }
            }

            // Update lock visuals
            if (isLocked) {
                entity.point.color = Cesium.Color.RED;
                entity.point.pixelSize = 12;
            } else {
                entity.point.color = (affiliation === 'FRIENDLY') ? Cesium.Color.SKYBLUE : Cesium.Color.RED;
                entity.point.pixelSize = 8;
            }

            // Waypoint Visualization
            const waypoint = (track.metadata && track.metadata.target_waypoint) ? track.metadata.target_waypoint : null;
            const wpId = `${trackId}-wp`;
            
            if (waypoint) {
                const wpPos = Cesium.Cartesian3.fromDegrees(waypoint[0], waypoint[1], alt);
                if (!this.entities[wpId]) {
                    this.entities[wpId] = this.viewer.entities.add({
                        id: wpId,
                        position: wpPos,
                        ellipse: {
                            semiMinorAxis: 200.0,
                            semiMajorAxis: 200.0,
                            material: Cesium.Color.SKYBLUE.withAlpha(0.2),
                            outline: true,
                            outlineColor: Cesium.Color.SKYBLUE,
                            height: alt,
                            heightReference: Cesium.HeightReference.NONE
                        },
                        polyline: {
                            positions: new Cesium.CallbackProperty(() => {
                                const dronePos = this.entities[trackId]?.position.getValue(Cesium.JulianDate.now());
                                return dronePos ? [dronePos, wpPos] : [];
                            }, false),
                            width: 1,
                            material: new Cesium.PolylineDashMaterialProperty({
                                color: Cesium.Color.SKYBLUE.withAlpha(0.5)
                            })
                        }
                    });
                } else {
                    this.entities[wpId].position = wpPos;
                    this.entities[wpId].ellipse.height = alt;
                }
            } else if (this.entities[wpId]) {
                this.viewer.entities.removeById(wpId);
                delete this.entities[wpId];
            }

            // Laser Painting Effect
            const isPainting = track.metadata && track.metadata.mode === 'painting';
            const targetId = track.metadata ? track.metadata.target_id : null;
            const laserId = `${trackId}-laser`;

            if (isPainting && targetId && this.entities[targetId]) {
                const targetPos = this.entities[targetId].position.getValue(Cesium.JulianDate.now());
                if (!this.entities[laserId]) {
                    this.entities[laserId] = this.viewer.entities.add({
                        id: laserId,
                        polyline: {
                            positions: new Cesium.CallbackProperty(() => {
                                const dronePos = this.entities[trackId].position.getValue(Cesium.JulianDate.now());
                                const tPos = this.entities[targetId]?.position.getValue(Cesium.JulianDate.now());
                                return tPos ? [dronePos, tPos] : [];
                            }, false),
                            width: 2,
                            material: new Cesium.PolylineGlowMaterialProperty({
                                glowPower: 0.2,
                                color: Cesium.Color.RED
                            })
                        }
                    });
                }
            } else if (this.entities[laserId]) {
                this.viewer.entities.removeById(laserId);
                delete this.entities[laserId];
            }
        });

        // Update Camera if in POV mode
        if (this.isPOVActive && this.trackedDroneId) {
            const drone = this.entities[this.trackedDroneId];
            if (drone) {
                this.viewer.trackedEntity = drone;
            }
        }
    }

    createTacticalEntity(id, type, affiliation, position) {
        const color = (affiliation === 'FRIENDLY') ? Cesium.Color.SKYBLUE : Cesium.Color.RED;
        const icon = this.getTacticalIcon(type);

        const entity = this.viewer.entities.add({
            id: id,
            name: `${type} [${id}]`,
            position: position,
            point: {
                pixelSize: 8,
                color: color,
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 2,
                heightReference: type === 'UAV' ? Cesium.HeightReference.NONE : Cesium.HeightReference.CLAMP_TO_GROUND
            },
            label: {
                text: id,
                font: '10px JetBrains Mono',
                fillColor: color,
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 2,
                style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                pixelOffset: new Cesium.Cartesian2(0, -15),
                distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 50000)
            }
        });

        if (type === 'UAV') {
            entity.model = {
                uri: 'resources/models/drone.glb',
                minimumPixelSize: 64,
                maximumScale: 20000,
                distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 5000)
            };
        }

        return entity;
    }

    getTacticalIcon(type) {
        // We'll use points for now, but in a real app we'd use billboards
        return null;
    }

    setPOV(droneId) {
        this.trackedDroneId = droneId;
        this.isPOVActive = !!droneId;
        if (!droneId) {
            this.viewer.trackedEntity = undefined;
        } else {
            const drone = this.entities[droneId];
            if (drone) {
                this.viewer.trackedEntity = drone;
                // Adjust view offset for cool perspective
                this.viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
            }
        }
    }
}
