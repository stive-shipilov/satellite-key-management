/* Circular orbits and an abstract disclosure model. No keys or network traffic. */
const OrbitScenario = (() => {
    "use strict";

    const radius = 6371;
    const earthGM = 398600.435507; // km³/s², JPL DE440
    const earthRotation = 2 * Math.PI * 60 / 86164.1; // radians per minute, sidereal day
    const radians = Math.PI / 180;
    const twoPi = 2 * Math.PI;

    function groundPoint(lat, lon) {
        const latitude = lat * radians, longitude = lon * radians;
        return [
            radius * Math.cos(latitude) * Math.cos(longitude),
            radius * Math.cos(latitude) * Math.sin(longitude),
            radius * Math.sin(latitude),
        ];
    }

    function visibleIds(positions, ground, mask) {
        const minSine = Math.sin(mask * radians);
        const [gx, gy, gz] = ground;
        const visible = [];
        positions.forEach(([x, y, z], i) => {
            const dx = x - gx, dy = y - gy, dz = z - gz;
            const sine = (dx * gx + dy * gy + dz * gz) / (radius * Math.hypot(dx, dy, dz));
            if (sine + 1e-12 >= minSine) visible.push(i + 1);
        });
        return visible;
    }

    function createGeometry(config, observer = null) {
        const {n, planes, altitude, inclination, lat, lon, mask, minutes} = config;
        const orbitRadius = radius + altitude;
        const omega = Math.sqrt(earthGM / orbitRadius ** 3) * 60;
        const station = groundPoint(lat, lon);
        const second = observer ? groundPoint(observer.lat, observer.lon) : null;
        const cosInc = Math.cos(inclination * radians), sinInc = Math.sin(inclination * radians);
        const stations = second ? [station, second] : [station];
        const planeData = Array.from({length: planes}, (_, plane) => {
            const count = Math.floor(n / planes) + Number(plane < n % planes);
            return {
                raan: twoPi * plane / planes,
                phases: Array.from({length: count}, (_, i) => twoPi * (i / count + plane / n)),
            };
        });

        function point(anomaly, ascendingCos, ascendingSin) {
            const inPlaneX = orbitRadius * Math.cos(anomaly);
            const inPlaneY = orbitRadius * Math.sin(anomaly);
            return [
                ascendingCos * inPlaneX - ascendingSin * cosInc * inPlaneY,
                ascendingSin * inPlaneX + ascendingCos * cosInc * inPlaneY,
                sinInc * inPlaneY,
            ];
        }

        function positionsAt(t) {
            return planeData.flatMap(({raan, phases}) => {
                const angle = raan - earthRotation * t;
                const cos = Math.cos(angle), sin = Math.sin(angle);
                return phases.map(phase => point(phase + omega * t, cos, sin));
            });
        }

        // Keep the drawing readable for dense constellations. Every plane is used for contacts.
        const drawnPlanes = Math.min(24, planes);
        const paths = Array.from({length: drawnPlanes}, (_, i) => {
            const {raan} = planeData[Math.floor(i * planes / drawnPlanes)];
            return Array.from({length: 97}, (_, j) => point(twoPi * j / 96, Math.cos(raan), Math.sin(raan)));
        });

        const contacts = Array.from({length: minutes}, (_, t) => {
            const positions = positionsAt(t);
            return {
                visible: visibleIds(positions, station, mask),
                observed: second ? visibleIds(positions, second, mask) : [],
            };
        });
        return {stations, paths, positionsAt, period: twoPi / omega, contacts};
    }

    function run(config, contacts, events) {
        const {k, n, refresh} = config;
        const byMinute = new Map();
        for (const event of events) {
            if (event.minute < 0 || event.minute >= contacts.length || event.sid > n) continue;
            if (!byMinute.has(event.minute)) byMinute.set(event.minute, []);
            byMinute.get(event.minute).push(event);
        }
        const persistent = new Set();
        const isolated = new Set();
        const known = new Set();
        let epoch = 1, session = 1, exposedKey = false;
        let first = null, outage = 0, longest = 0, available = 0, exposedMinutes = 0;
        let lastDistribution = 0;
        const history = contacts.map(({visible, observed}, minute) => {
            const now = byMinute.get(minute) ?? [];
            // Isolation/recovery applies before this minute's distribution and disclosures.
            for (const {kind, sid} of now) {
                if (kind === "isolate") {
                    isolated.add(sid);
                    persistent.delete(sid);
                } else if (kind === "restore") {
                    isolated.delete(sid);
                    persistent.delete(sid);
                }
            }
            const rotated = now.some(event => event.kind === "rotate");
            const refreshed = refresh > 0 && minute - lastDistribution >= refresh;
            if (rotated || refreshed) {
                known.clear();
                lastDistribution = minute;
                if (rotated) {
                    session++;
                    exposedKey = false;
                    epoch = 1;
                } else epoch++;
            }
            const disclosed = [];
            for (const {kind, sid} of now) {
                if (isolated.has(sid)) continue;
                if (kind === "persist") persistent.add(sid);
                if (kind === "reveal" && !known.has(sid)) {
                    known.add(sid);
                    disclosed.push(sid);
                }
            }
            for (const sid of persistent) {
                if (!known.has(sid)) {
                    known.add(sid);
                    disclosed.push(sid);
                }
            }
            const disclosedKey = now.some(event => event.kind === "key");
            const newlyExposed = !exposedKey && (known.size >= k || disclosedKey);
            if (newlyExposed) {
                exposedKey = true;
                first ??= minute;
            }

            const received = visible.filter(sid => !isolated.has(sid));
            const ready = received.length >= k;
            if (ready) {
                available++;
                outage = 0;
            } else {
                outage++;
                longest = Math.max(longest, outage);
            }
            if (exposedKey) exposedMinutes++;
            return {
                visible, observed, received, ready,
                isolated: [...isolated], exposed: [...known], disclosed,
                exposedKey, newlyExposed, disclosedKey, epoch, session, rotated, refreshed: refreshed && !rotated,
            };
        });
        return {history, summary: {first, longest, available, exposedMinutes}};
    }

    function example(config, outcome) {
        const last = Math.min(config.minutes, config.refresh || config.minutes) - 1;
        const count = outcome === "quorum" ? config.k : config.k - 1;
        return Array.from({length: count}, (_, i) => ({
            kind: "reveal", sid: i + 1, minute: Math.floor(last * (i + 1) / Math.max(1, config.k)),
        }));
    }

    return {radius, earthRotation, groundPoint, visibleIds, createGeometry, run, example};
})();

if (typeof module !== "undefined") module.exports = OrbitScenario;
