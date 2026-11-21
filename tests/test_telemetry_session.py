from dataclasses import replace

import pytest
from cryptography.exceptions import InvalidTag

from satellite_key_management.simulation.leo_model import LEOModel
from satellite_key_management.simulation.telemetry import TelemetrySession


@pytest.mark.parametrize("name,k", [("shamir", 2), ("blakley", 2), ("xor", 3), ("crt", 3)])
def test_delivery_across_visibility_change(name, k, monkeypatch):
    # Ведущие нули ключа должны сохраниться при переходе int → AES bytes.
    monkeypatch.setattr("satellite_key_management.simulation.telemetry.secrets.token_bytes",
                        lambda n: bytes(n - 1) + b"\x07")
    leo = LEOModel(n_sats=72, n_planes=6, seed=7)
    members = leo.visible_at(53)
    assert members == [8, 69, 70] and leo.visible_at(54) == [8, 69]
    session = TelemetrySession.issue(name, members, k, b"voltage=12", b"frame-01")
    assert session.receive(leo, 53) == b"voltage=12"
    assert session.receive(leo, 54) == (b"voltage=12" if k == 2 else None)
    with pytest.raises(InvalidTag):
        replace(session, aad=b"frame-02").receive(leo, 53)


@pytest.mark.parametrize("name,members,k", [
    ("xor", [8, 69, 70], 2), ("crt", [8, 69, 70], 2), ("blakley", [8, 8], 2),
    ("shamir", [8], 2), ("unknown", [8], 1),
])
def test_invalid_telemetry_session(name, members, k):
    with pytest.raises(ValueError):
        TelemetrySession.issue(name, members, k, b"frame")
