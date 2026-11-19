"""LEO-модель с 3D-позициями (км), подспутниковой точкой и зоной покрытия."""
import numpy as np

R_EARTH = 6371.0  # км

class Satellite:
    def __init__(self, sid, raan, inc=53.0, altitude=550.0, phase0=0.0):
        self.sid = sid
        self.raan = np.radians(raan)          # прямое восхождение узла
        self.inc = np.radians(inc)
        self.altitude = altitude
        self.phase0 = np.radians(phase0)
        self.omega = 2 * np.pi / 95.0         # рад/мин (~95 мин виток)

    def position(self, t_min):
        """3D-позиция в ECI-подобной системе (км)."""
        u = self.phase0 + self.omega * t_min        # аргумент широты
        r = R_EARTH + self.altitude
        x = r * (np.cos(self.raan) * np.cos(u) - np.sin(self.raan) * np.sin(u) * np.cos(self.inc))
        y = r * (np.sin(self.raan) * np.cos(u) + np.cos(self.raan) * np.sin(u) * np.cos(self.inc))
        z = r * (np.sin(u) * np.sin(self.inc))
        return np.array([x, y, z])

    def subpoint(self, t_min):
        """Подспутниковая точка на сфере Земли (единичный вектор * R_EARTH)."""
        p = self.position(t_min)
        return p / np.linalg.norm(p) * R_EARTH

class LEOModel:
    def __init__(self, n_sats=12, seed=42, n_planes=3):
        rng = np.random.default_rng(seed)
        self.sats = []
        if n_sats < 1 or n_planes < 1:
            raise ValueError('Число спутников и плоскостей должно быть положительным')
        base, extra = divmod(n_sats, n_planes)
        for p in range(n_planes):
            per_plane = base + int(p < extra)
            raan = p * (360.0 / n_planes)
            for i in range(per_plane):
                phase = i * (360.0 / per_plane) + rng.uniform(-5, 5)
                self.sats.append(Satellite(len(self.sats) + 1, raan, phase0=phase))

    def visible_at(self, t_min, gs_lat=55.0, gs_lon=37.0, min_elev_deg=10.0,
                   radius_km=None):
        """
        Если radius_km задан — видимость по попаданию подспутниковой точки
        в кольцо радиуса radius_km вокруг GS (совпадает с нарисованным кольцом).
        Иначе — по углу места (старое поведение).
        """
        gs = self._gs_vector(gs_lat, gs_lon)
        if radius_km is not None:
            visible = []
            for s in self.sats:
                sub = s.subpoint(t_min)
                # угловое расстояние между GS и подспутниковой точкой
                cos_ang = np.dot(gs, sub) / (np.linalg.norm(gs) * np.linalg.norm(sub))
                ang = np.arccos(np.clip(cos_ang, -1, 1))
                if ang * R_EARTH <= radius_km:
                    visible.append(s.sid)
            return visible

        # старое поведение по углу места
        up = gs / np.linalg.norm(gs)
        visible = []
        for s in self.sats:
            p = s.position(t_min)
            los = p - gs
            elev = np.degrees(np.arcsin(np.dot(los, up) / np.linalg.norm(los)))
            if elev >= min_elev_deg:
                visible.append(s.sid)
        return visible

    @staticmethod
    def _gs_vector(lat_deg, lon_deg):
        lat, lon = np.radians(lat_deg), np.radians(lon_deg)
        return R_EARTH * np.array([
            np.cos(lat) * np.cos(lon),
            np.cos(lat) * np.sin(lon),
            np.sin(lat),
        ])

    def visible_from(self, t_min, lat, lon, min_elev_deg=10.0):
        """Видимость из произвольной точки (для вражеской GS)."""
        return self.visible_at(t_min, lat, lon, min_elev_deg)
