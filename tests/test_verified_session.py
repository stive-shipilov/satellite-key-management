import pytest
from cryptography.exceptions import InvalidTag

from satellite_key_management.attacks.attacks import AttackerTracker, evil_dealer, share_accumulation
from satellite_key_management.simulation.contact_session import (
    ContactSchedule,
    session_history,
)
from satellite_key_management.simulation.leo_model import LEOModel
from satellite_key_management.simulation.session import ReplayRejected, SessionSimulator


def test_vss_rejects_wrong_participant_and_changed_share():
    sim = SessionSimulator(ContactSchedule(), 6, 2)
    sim.distribute()
    assert evil_dealer(sim, 6)[0]
    sim.shares[2] = sim.shares[1]
    assert sim.verified_key([1, 2]) == (None, 1)
    assert sim.verified_key([1, 2, 3]) == (sim.secret_key, 2)


def test_refresh_and_handover_preserve_receiver_state():
    sim = SessionSimulator(ContactSchedule(), 6, 2)
    sim.distribute()
    packet = sim.seal(b"first")
    assert sim.receive(packet, [1]) is None
    assert sim.receive(packet, [1, 2]) == b"first"
    old = sim.shares.copy()
    sim.refresh()
    assert sim.verified_key([2, 3])[0] == sim.secret_key
    assert not sim.vss.verify_share(old[1], sim.commitments)
    assert sim.last_received == packet[0]
    with pytest.raises(ReplayRejected):
        sim.receive(packet, [2, 3])
    assert sim.receive(sim.seal(b"second"), [2, 3]) == b"second" and sim.relay == 2


def test_incomplete_refresh_preserves_active_epoch():
    sim = SessionSimulator(ContactSchedule(), 3, 2)
    shares = sim.distribute()
    commitments = sim.commitments
    shares[3] = None
    with pytest.raises(ValueError, match="полный набор"):
        sim.refresh()
    assert sim.epoch == 1 and sim.shares is shares and sim.commitments is commitments
    assert sim.receive(sim.seal(b"existing epoch"), [1, 2, 3]) == b"existing epoch"


def test_replay_is_rejected_after_handover():
    sim = SessionSimulator(ContactSchedule(), 3, 2)
    sim.distribute()
    first = sim.seal(b"first")
    assert sim.receive(first, [1, 2]) == b"first"
    assert sim.receive(sim.seal(b"second"), [2, 3]) == b"second"
    assert sim.relay == 2
    with pytest.raises(ReplayRejected):
        sim.receive(first, [2, 3])


def test_invalid_tag_does_not_update_receive_window():
    sim = SessionSimulator(ContactSchedule(), 3, 2)
    sim.distribute()
    second = sim.seal(b"second")
    nonce, ct, tag = second[1]
    with pytest.raises(InvalidTag):
        sim.receive((second[0], (nonce, ct, bytes(16))), [2, 3])
    assert sim.last_received == -1 and sim.relay is None
    assert sim.receive(second, [2, 3]) == b"second" and sim.relay == 2


def test_receive_window_admits_out_of_order_packet_once():
    sim = SessionSimulator(ContactSchedule(), 3, 2, replay_window=2)
    sim.distribute()
    first, second, third = (sim.seal(bytes([index])) for index in range(3))
    assert sim.receive(third, [1, 2]) == b"\x02"
    assert sim.receive(second, [1, 2]) == b"\x01"
    assert sim.last_received == third[0]
    for rejected in (first, second):
        with pytest.raises(ReplayRejected):
            sim.receive(rejected, [1, 2])


def test_packet_rejected_in_new_session_context():
    original = SessionSimulator(ContactSchedule(), 3, 2)
    original.distribute()
    previous = original.seal(b"old session")
    restarted = SessionSimulator(ContactSchedule(), 3, 2)
    restarted.secret_key = original.secret_key  # изолируем проверку контекста от проверки ключа
    restarted.distribute()
    with pytest.raises(InvalidTag):
        restarted.receive(previous, [1, 2])
    assert restarted.receive(restarted.seal(b"new session"), [1, 2]) == b"new session"


def test_tracker_counts_only_explicit_exposures_and_retains_disclosed_key():
    sim = SessionSimulator(ContactSchedule(), 3, 2)
    sim.distribute()
    tracker = AttackerTracker(sim)
    assert tracker.step(0, [1, 2, 3]).shares == 0
    assert tracker.step(1, [3], [1, 1]).shares == 1
    assert tracker.step(2, [], [2]).key_exposed
    sim.refresh()
    updated = tracker.step(3, [1, 2, 3])
    assert updated.shares == 0 and updated.key_exposed
    assert tracker.refreshes == 1 and tracker.time_to_compromise() == 2
    old_packet = sim.seal(b"old key")
    sim.rotate_key()
    assert sim.k == 2
    assert not tracker.step(4, [1, 2, 3]).key_exposed
    with pytest.raises(InvalidTag):
        sim.receive(old_packet, [1, 2])
    assert sim.receive(sim.seal(b"new key"), [1, 2]) == b"new key"


def test_actual_epoch_sawtooth_does_not_modify_live_shares():
    sim = SessionSimulator(ContactSchedule(), 6, 2)
    original = sim.distribute()
    assert share_accumulation(sim, 8, 3) == [1, 2, 3, 1, 2, 3, 1, 2]
    assert sim.shares is original and sim.epoch == 1


def test_contact_windows_and_signed_delivery():
    schedule = ContactSchedule()
    for sid, duration in enumerate(schedule.durations, 1):
        start = (sid - 1) * 3
        assert 6 <= duration <= 12
        assert sid not in schedule.visible_at(start - 1)
        assert all(
            sid in schedule.visible_at(t) for t in range(start, start + duration)
        )
        assert sid not in schedule.visible_at(start + duration)
    history = session_history(35)
    assert all(r.delivered for r in history) and any(r.handover for r in history)
    assert history[-1].epoch == 2
    assert any(r.signature_verified and r.replay_rejected and r.replay_reason == "duplicate"
               for r in history)


def test_constellation_keeps_remainder():
    assert len(LEOModel(n_sats=7, n_planes=3).sats) == 7


@pytest.mark.parametrize("invalid", [None, (), (1,), (1, "bad"), (1, 2, 3)])
def test_malformed_record_does_not_block_honest_quorum(invalid):
    sim = SessionSimulator(ContactSchedule(), 3, 2)
    sim.distribute()
    sim.shares[1] = invalid
    packet = sim.seal(b"payload")
    assert sim.receive(packet, [1, 2]) is None
    assert sim.receive(packet, [1, 2, 3]) == b"payload"


def test_required_signature_checked_before_advancing_sequence():
    from satellite_key_management.crypto.threshold_sig import generate_key, sign_share

    keys, shares = generate_key(1, 1)
    sim = SessionSimulator(ContactSchedule(), 1, 1, initial_signer=keys.public_key)
    sim.distribute()
    with pytest.raises(ValueError, match="подпись"):
        sim.receive(sim.seal(b"message"), [1])
    assert sim.last_received == -1 and sim.relay is None
    signature = sign_share(shares[0], sim.signing_payload(sim.next_sequence, b"message"))[1]
    assert sim.receive(sim.seal(b"message" + signature), [1]) == b"message"
