const {test} = require("node:test");
const assert = require("node:assert/strict");
const {createGeometry, groundPoint, visibleIds, run, example} =
    require("../src/satellite_key_management/visualization/orbit-scenario.js");

const config = {
    n: 4, planes: 2, k: 3, refresh: 3, minutes: 8,
    altitude: 550, inclination: 53, lat: 0, lon: 0, mask: 10,
};
const contacts = Array.from({length: config.minutes}, () => ({visible: [1, 2, 3], observed: [1, 2, 3, 4]}));

test("geometry uses the same angular mask, preserves altitude, and includes all satellites", () => {
    const geometry = createGeometry(config, {lat: config.lat, lon: config.lon});
    assert.ok(Math.abs(geometry.period - 95.5) < 0.05);
    assert.equal(geometry.paths.length, 2);
    assert.equal(geometry.positionsAt(2.5).length, 4);
    for (const position of geometry.positionsAt(2.5)) {
        assert.ok(Math.abs(Math.hypot(...position) - 6921) < 1e-8);
    }
    for (const {visible, observed} of geometry.contacts) assert.deepEqual(visible, observed);
    assert.deepEqual(visibleIds([[6921, 0, 0], [-6921, 0, 0], [6371, 1000, 0]], groundPoint(0, 0), 10), [1]);
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

test("examples straddle the threshold even in a one-minute epoch", () => {
    for (const refresh of [0, 1, 3]) {
        const scenario = {...config, refresh};
        const safe = run(scenario, contacts, example(scenario, "below"));
        const reached = run(scenario, contacts, example(scenario, "quorum"));
        assert.equal(safe.summary.first, null);
        assert.notEqual(reached.summary.first, null);
    }
});
