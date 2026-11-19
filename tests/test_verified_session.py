import pytest
from cryptography.exceptions import InvalidTag

from satellite_key_management.attacks.attacks import evil_dealer, share_accumulation
from satellite_key_management.simulation.contact_session import (
    ContactSchedule,
    session_history,
)
from satellite_key_management.simulation.leo_model import LEOModel
from satellite_key_management.simulation.session import SessionSimulator


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
    with pytest.raises(ValueError, match="номер пакета"):
        sim.receive(packet, [2, 3])
    second = sim.seal(b"second")
    nonce, ct, tag = second[1]
    with pytest.raises(InvalidTag):
        sim.receive((second[0], (nonce, ct, bytes(16))), [2, 3])
    assert sim.receive(second, [2, 3]) == b"second" and sim.relay == 2


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
    assert any(r.signature_verified and r.replay_rejected for r in history)


def test_constellation_keeps_remainder():
    assert len(LEOModel(n_sats=7, n_planes=3).sats) == 7
