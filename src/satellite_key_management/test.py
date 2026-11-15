from simulation.leo_model import LEOModel
from simulation.session import SessionSimulator

leo = LEOModel(n_sats=36, seed=7, n_planes=6)
sim = SessionSimulator(leo, n=36, k=12)
sim.distribute()

# диагностика зоны
gs_lat, gs_lon = -30.0, -60.0
for t in range(0, 120, 10):
    in_zone = leo.visible_at(t, -30.0, -60.0, radius_km=2500)
    print(f"t={t:3d}  в зоне: {in_zone}")