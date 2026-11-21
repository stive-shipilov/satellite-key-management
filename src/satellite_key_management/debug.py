from satellite_key_management.simulation.leo_model import LEOModel
from satellite_key_management.simulation.session import SessionSimulator
leo = LEOModel(n_sats=36, seed=7, n_planes=6)
sim = SessionSimulator(leo, n=36, k=3, scheme="blakley", bits=128)
sim.distribute()
for t in (0, 30, 60, 90):
    v = leo.visible_at(t, 55.0, 37.0, radius_km=3000)
    print(f"t={t}: visible={len(v)}, valid={len(sim._valid_shares(v))}, k={sim.k}")