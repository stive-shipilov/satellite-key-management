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

    function visibleIds(positions, ground, mask, ids = null) {
        const minSine = Math.sin(mask * radians);
        const [gx, gy, gz] = ground;
        const visible = [];
        positions.forEach(([x, y, z], i) => {
            const dx = x - gx, dy = y - gy, dz = z - gz;
            const sine = (dx * gx + dy * gy + dz * gz) / (radius * Math.hypot(dx, dy, dz));
            if (sine + 1e-12 >= minSine) visible.push(ids ? ids[i] : i + 1);
        });
        return visible;
    }

    function groupsFor(config) {
        return config.groups ?? [{n: config.n, planes: config.planes,
            altitude: config.altitude, inclination: config.inclination}];
    }

    function satelliteIds(groups) {
        return groups.flatMap(({n}, group) =>
            Array.from({length: n}, (_, i) => group * 1000 + i + 1));
    }

    function createShell({n, planes, altitude, inclination}, group) {
        const orbitRadius = radius + altitude;
        const omega = Math.sqrt(earthGM / orbitRadius ** 3) * 60;
        const cosInc = Math.cos(inclination * radians), sinInc = Math.sin(inclination * radians);
        const planeData = Array.from({length: planes}, (_, plane) => {
            const count = Math.floor(n / planes) + Number(plane < n % planes);
            return {
                raan: twoPi * (plane + group / 3) / planes,
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

        // Cap the drawn paths. Every plane still contributes to the contact trace.
        const drawnPlanes = Math.min(12, planes);
        const paths = Array.from({length: drawnPlanes}, (_, i) => {
            const {raan} = planeData[Math.floor(i * planes / drawnPlanes)];
            const cos = Math.cos(raan), sin = Math.sin(raan);
            return Array.from({length: 97}, (_, j) => point(twoPi * j / 96, cos, sin));
        });
        return {paths, positionsAt, period: twoPi / omega};
    }

    function createGeometry(config, observer = null) {
        const {lat, lon, mask, minutes} = config;
        const groups = groupsFor(config);
        const shells = groups.map(createShell);
        const ids = satelliteIds(groups);
        const station = groundPoint(lat, lon);
        const second = observer ? groundPoint(observer.lat, observer.lon) : null;
        const stations = second ? [station, second] : [station];
        const positionsAt = t => shells.flatMap(shell => shell.positionsAt(t));
        const contacts = Array.from({length: minutes}, (_, t) => {
            const positions = positionsAt(t);
            return {
                visible: visibleIds(positions, station, mask, ids),
                observed: second ? visibleIds(positions, second, mask, ids) : [],
            };
        });
        return {stations, shells, ids, positionsAt, contacts};
    }

    function sessionTransitions({refresh, rotation = 0}, minutes, manualRotations = new Set()) {
        let lastRotation = 0, lastDistribution = 0;
        return Array.from({length: minutes}, (_, minute) => {
            if (manualRotations.has(minute) || (rotation > 0 && minute - lastRotation >= rotation)) {
                lastRotation = lastDistribution = minute;
                return "rotate";
            }
            if (refresh > 0 && minute - lastDistribution >= refresh) {
                lastDistribution = minute;
                return "refresh";
            }
            return null;
        });
    }

    function run(config, contacts, events) {
        const {k} = config;
        const ids = new Set(satelliteIds(groupsFor(config)));
        const byMinute = new Map();
        for (const event of events) {
            if (event.minute < 0 || event.minute >= contacts.length || (event.sid != null && !ids.has(event.sid))) continue;
            if (!byMinute.has(event.minute)) byMinute.set(event.minute, []);
            byMinute.get(event.minute).push(event);
        }
        const persistent = new Set();
        const isolated = new Set();
        const known = new Set();
        let epoch = 1, session = 1, exposedKey = false;
        let first = null, outage = 0, longest = 0, available = 0, exposedMinutes = 0;
        const manualRotations = new Set([...byMinute].filter(([, items]) => items.some(event => event.kind === "rotate"))
            .map(([minute]) => minute));
        const transitions = sessionTransitions(config, contacts.length, manualRotations);
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
            const rotated = transitions[minute] === "rotate";
            const refreshed = transitions[minute] === "refresh";
            if (rotated || refreshed) {
                known.clear();
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
                exposedKey, newlyExposed, disclosedKey, epoch, session, rotated, refreshed,
            };
        });
        return {history, summary: {first, longest, available, exposedMinutes}};
    }

    function example(config, outcome) {
        const last = Math.min(config.minutes, config.refresh || config.minutes, config.rotation || config.minutes) - 1;
        const count = outcome === "quorum" ? config.k : config.k - 1;
        return satelliteIds(groupsFor(config)).slice(0, count).map((sid, i) => ({
            kind: "reveal", sid, minute: Math.floor(last * (i + 1) / config.k),
        }));
    }

    function windowDraw(seed, sid, start) {
        // A stable draw for this virtual window, even when playback or the duration setting changes.
        let value = seed ^ Math.imul(sid, 0x9e3779b1) ^ Math.imul(start + 1, 0x85ebca77);
        value = Math.imul(value ^ (value >>> 16), 0x21f0aaad);
        value = Math.imul(value ^ (value >>> 15), 0x735a2d97);
        return ((value ^ (value >>> 15)) >>> 0) / 0x100000000;
    }

    function contactRisk(config, contacts, profile) {
        const {duration, probability, seed} = profile;
        const windows = new Map();
        const known = new Set();
        const events = [], log = [];
        const transitions = sessionTransitions(config, contacts.length);
        const record = (minute, sid, window, status) =>
            log.push({minute, sid, elapsed: window.elapsed, status});
        const progress = contacts.map(({observed}, minute) => {
            if (transitions[minute]) {
                const status = transitions[minute] === "rotate" ? "rotated" : "refreshed";
                for (const [sid, window] of windows) {
                    if (window.status === "waiting") record(minute, sid, window, status);
                }
                windows.clear();
                known.clear();
            }
            const visible = new Set(observed);
            for (const [sid, window] of windows) {
                if (visible.has(sid)) continue;
                if (window.status === "waiting") record(minute, sid, window, "interrupted");
                windows.delete(sid);
            }
            return observed.map(sid => {
                let window = windows.get(sid);
                if (!window) {
                    window = {start: minute, elapsed: 0, status: known.has(sid) ? "known" : "waiting"};
                    windows.set(sid, window);
                }
                window.elapsed = minute - window.start;
                if (window.status === "waiting" && window.elapsed >= duration) {
                    const revealed = windowDraw(seed, sid, window.start) < probability;
                    window.status = revealed ? "revealed" : "failed";
                    record(minute, sid, window, window.status);
                    if (revealed) {
                        known.add(sid);
                        events.push({minute, sid, kind: "reveal"});
                    }
                }
                return {sid, elapsed: window.elapsed, status: window.status};
            });
        });
        return {events, log, progress};
    }

    return {radius, earthRotation, groundPoint, visibleIds, groupsFor, createGeometry, run, example, contactRisk};
})();

if (typeof module !== "undefined") module.exports = OrbitScenario;
