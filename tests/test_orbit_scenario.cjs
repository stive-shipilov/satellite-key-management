const {test} = require("node:test");
const assert = require("node:assert/strict");
const {createGeometry, groundPoint, visibleIds, run, example, contactRisk} =
    require("../src/satellite_key_management/visualization/orbit-scenario.js");

const config = {
    n: 4, planes: 2, k: 3, refresh: 3, minutes: 8,
    altitude: 550, inclination: 53, lat: 0, lon: 0, mask: 10,
};
const contacts = Array.from({length: config.minutes}, () => ({visible: [1, 2, 3], observed: [1, 2, 3, 4]}));

test("geometry uses the same angular mask, preserves altitude, and includes all satellites", () => {
    const geometry = createGeometry(config, {lat: config.lat, lon: config.lon});
    assert.ok(Math.abs(geometry.shells[0].period - 95.5) < 0.05);
    assert.equal(geometry.shells[0].paths.length, 2);
    assert.equal(geometry.positionsAt(2.5).length, 4);
    for (const position of geometry.positionsAt(2.5)) {
        assert.ok(Math.abs(Math.hypot(...position) - 6921) < 1e-8);
    }
    for (const {visible, observed} of geometry.contacts) assert.deepEqual(visible, observed);
    assert.deepEqual(visibleIds([[6921, 0, 0], [-6921, 0, 0], [6371, 1000, 0]], groundPoint(0, 0), 10), [1]);
});

test("mixed shells retain separate orbital parameters and stable satellite IDs", () => {
    const groups = [
        {n: 2, planes: 1, altitude: 550, inclination: 53},
        {n: 3, planes: 2, altitude: 1200, inclination: 87.9},
        {n: 1, planes: 1, altitude: 705, inclination: 98.2},
    ];
    const mixed = {...config, groups};
    const geometry = createGeometry(mixed);
    assert.deepEqual(geometry.ids, [1, 2, 1001, 1002, 1003, 2001]);
    assert.deepEqual(geometry.shells.map(shell => shell.paths.length), [1, 2, 1]);
    assert.deepEqual(geometry.positionsAt(3.5).map(point => Math.round(Math.hypot(...point))),
        [6921, 6921, 7571, 7571, 7571, 7076]);
    assert.equal(new Set(geometry.shells.map(shell => shell.period)).size, 3);
    const events = [{kind: "reveal", sid: 1002, minute: 0}, {kind: "reveal", sid: 2, minute: 0}];
    const shrunk = {...mixed, groups: [{...groups[0], n: 1}, groups[1]]};
    assert.deepEqual(run(shrunk, createGeometry(shrunk).contacts, events).history[0].exposed, [1002]);
});

test("moving the radio observer changes its contacts independently of reception and disclosures", () => {
    const near = createGeometry(config, {lat: 0, lon: 0});
    const far = createGeometry(config, {lat: 0, lon: 180});
    assert.notDeepEqual(near.contacts[0].observed, far.contacts[0].observed);
    assert.deepEqual(near.contacts.map(row => row.visible), far.contacts.map(row => row.visible));
    const events = [{minute: 0, kind: "reveal", sid: 1}];
    assert.deepEqual(run(config, near.contacts, events).summary, run(config, far.contacts, events).summary);
});

test("only distinct shares from the current epoch count and observation does not disclose them", () => {
    const events = [
        {minute: 0, kind: "reveal", sid: 1},
        {minute: 1, kind: "reveal", sid: 1},
        {minute: 2, kind: "reveal", sid: 2},
        {minute: 3, kind: "reveal", sid: 3},
    ];
    const {history, summary} = run(config, contacts, events);
    assert.ok(history.every(row => row.ready));
    assert.deepEqual(history.map(row => row.exposed.length), [1, 1, 2, 1, 1, 1, 0, 0]);
    assert.equal(summary.first, null);
    assert.deepEqual(history[1].disclosed, []);
});

test("compromise survives refresh and rotation clears the key after isolation", () => {
    const events = [
        {minute: 0, kind: "persist", sid: 1},
        {minute: 1, kind: "reveal", sid: 2},
        {minute: 2, kind: "reveal", sid: 3},
        {minute: 4, kind: "isolate", sid: 1},
        {minute: 4, kind: "rotate"},
        {minute: 5, kind: "restore", sid: 1},
    ];
    const {history, summary} = run(config, contacts, events);
    assert.equal(summary.first, 2);
    assert.equal(summary.exposedMinutes, 2);
    assert.equal(summary.longest, 1);
    assert.equal(history[3].exposedKey, true);
    assert.deepEqual(history[3].disclosed, [1]);
    assert.equal(history[4].exposedKey, false);
    assert.equal(history[4].ready, false);
    assert.equal(history[4].session, 2);
    assert.deepEqual(history[5].exposed, []);
    assert.equal(history[5].ready, true);
    assert.equal(history[6].refreshed, false);
    assert.equal(history[7].refreshed, true);
});

test("rotation alone leaves a persistent disclosure in the new session", () => {
    const {history} = run({...config, k: 1}, contacts, [
        {minute: 0, kind: "persist", sid: 1},
        {minute: 1, kind: "rotate"},
    ]);
    assert.equal(history[1].exposedKey, true);
    assert.deepEqual(history[1].disclosed, [1]);
});

test("automatic key rotation starts a clean session and restarts the refresh clock", () => {
    const trace = Array.from({length: 10}, () => ({visible: [], observed: []}));
    const scenario = {...config, rotation: 4, refresh: 3};
    const events = [1, 2, 3].map(sid => ({minute: 0, kind: "reveal", sid}));
    const {history, summary} = run(scenario, trace, events);
    assert.equal(history[3].refreshed, true);
    assert.equal(history[3].exposedKey, true);
    assert.equal(history[4].rotated, true);
    assert.equal(history[4].exposedKey, false);
    assert.deepEqual([history[4].session, history[4].epoch], [2, 1]);
    assert.equal(history[6].refreshed, false);
    assert.equal(history[7].refreshed, true);
    assert.equal(history[8].session, 3);
    assert.equal(summary.exposedMinutes, 4);
    const manual = run(scenario, trace, [...events, {minute: 2, kind: "rotate"}]).history;
    assert.equal(manual[4].rotated, false);
    assert.equal(manual[6].rotated, true);
});

test("examples straddle the threshold even in a one-minute epoch", () => {
    for (const refresh of [0, 1, 3]) {
        const scenario = {...config, refresh};
        const safe = run(scenario, contacts, example(scenario, "below"));
        const reached = run(scenario, contacts, example(scenario, "quorum"));
        assert.equal(safe.summary.first, null);
        assert.notEqual(reached.summary.first, null);
    }
});

test("continuous contact starts at zero and a visibility gap discards elapsed time", () => {
    const trace = [[1], [1], [], [1], [1], [1], [1]].map(observed => ({observed, visible: [1, 2, 3]}));
    const risk = contactRisk({...config, refresh: 0}, trace, {duration: 2, probability: 1, seed: 7});
    assert.deepEqual(risk.events, [{minute: 5, sid: 1, kind: "reveal"}]);
    assert.deepEqual(risk.log[0], {minute: 2, sid: 1, elapsed: 1, status: "interrupted"});
    assert.equal(risk.progress[0][0].elapsed, 0);
    assert.equal(risk.progress[3][0].elapsed, 0);
    assert.equal(run(config, trace, risk.events).summary.available, trace.length);
});

test("risk is checked once per window and discards partial contact on refresh", () => {
    const trace = Array.from({length: 5}, () => ({observed: [1], visible: []}));
    const profile = {duration: 2, probability: 0, seed: 7};
    const failed = contactRisk({...config, refresh: 0}, trace, profile);
    assert.deepEqual(failed.events, []);
    assert.deepEqual(failed.log, [{minute: 2, sid: 1, elapsed: 2, status: "failed"}]);
    const refreshed = contactRisk({...config, refresh: 2}, trace, {...profile, probability: 1});
    assert.deepEqual(refreshed.events, []);
    assert.deepEqual(refreshed.log, [2, 4].map(minute => ({minute, sid: 1, elapsed: 1, status: "refreshed"})));
});

test("a key rotation interrupts contact progress and takes precedence over a scheduled refresh", () => {
    const trace = Array.from({length: 6}, () => ({observed: [1], visible: []}));
    const scenario = {...config, refresh: 3, rotation: 3, k: 1};
    const risk = contactRisk(scenario, trace, {duration: 2, probability: 1, seed: 7});
    assert.deepEqual(risk.events.map(({minute}) => minute), [2, 5]);
    assert.equal(risk.progress[3][0].elapsed, 0);
    const {history} = run(scenario, trace, risk.events);
    assert.equal(history[3].rotated, true);
    assert.equal(history[3].refreshed, false);
    assert.equal(history[3].exposedKey, false);
    assert.equal(history[5].exposedKey, true);
});

test("a seed reproduces the window outcomes and reacquiring the same share adds no duplicate", () => {
    const scenario = {...config, refresh: 0, k: 2};
    const trace = [[1, 2], [1, 2], [], [1], [1]].map(observed => ({observed, visible: []}));
    const profile = {duration: 1, probability: 0.5, seed: 7};
    assert.deepEqual(contactRisk(scenario, trace, profile), contactRisk(scenario, trace, profile));
    const certain = contactRisk(scenario, trace, {...profile, probability: 1});
    assert.deepEqual(certain.events.map(event => event.sid), [1, 2]);
    assert.equal(certain.progress[4][0].status, "known");
    assert.equal(run(scenario, trace, certain.events).summary.first, 1);
});
