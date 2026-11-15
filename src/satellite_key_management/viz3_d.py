import numpy as np
import plotly.graph_objects as go

# ==========================================
# 1. ГЕНЕРАЦИЯ ЗЕМЛИ (СФЕРА С ТЕКСТУРОЙ)
# ==========================================
# Используем встроенную текстуру Земли из Plotly
R_earth = 6371  # Радиус Земли в км

# Создаем сетку для сферы
phi, theta = np.mgrid[0:np.pi:100j, 0:2 * np.pi:100j]
x_earth = R_earth * np.sin(phi) * np.cos(theta)
y_earth = R_earth * np.sin(phi) * np.sin(theta)
z_earth = R_earth * np.cos(phi)

earth_trace = go.Surface(
    x=x_earth, y=y_earth, z=z_earth,
    colorscale='Blues',  # Имитация океанов (можно заменить на текстуру)
    opacity=0.9,
    showscale=False,
    name='Земля'
)

# ==========================================
# 2. ДАННЫЕ ДЛЯ СИМУЛЯЦИИ
# ==========================================
# Координаты наземной станции (например, Москва)
station_lat, station_lon = 55.75, 37.61


def lat_lon_to_xyz(lat, lon, r):
    lat_rad, lon_rad = np.radians(lat), np.radians(lon)
    return (r * np.cos(lat_rad) * np.cos(lon_rad),
            r * np.cos(lat_rad) * np.sin(lon_rad),
            r * np.sin(lat_rad))


st_x, st_y, st_z = lat_lon_to_xyz(station_lat, station_lon, R_earth)

# Зона покрытия станции (конус, направленный в космос)
cone_height = 1500  # Высота зоны покрытия в км
cone_radius = 1000  # Радиус основания конуса в км

# Создаем сетку для конуса
u = np.linspace(0, 2 * np.pi, 50)
v = np.linspace(0, 1, 20)
U, V = np.meshgrid(u, v)

# Локальные координаты конуса (вершина в начале координат)
cone_x = cone_radius * V * np.cos(U)
cone_y = cone_radius * V * np.sin(U)
cone_z = cone_height * V

# Поворачиваем конус так, чтобы он смотрел от Земли наружу
# (вдоль вектора нормали к поверхности в точке станции)
normal = np.array([st_x, st_y, st_z]) / np.linalg.norm([st_x, st_y, st_z])
up = np.array([0, 0, 1])
axis = np.cross(up, normal)
angle = np.arccos(np.dot(up, normal))

if np.linalg.norm(axis) > 1e-6:
    axis = axis / np.linalg.norm(axis)
    # Матрица поворота (Родрига)
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * np.dot(K, K)
else:
    R = np.eye(3)

# Применяем поворот и сдвиг к конусу
cone_xyz = np.dot(R, np.vstack([cone_x.flatten(), cone_y.flatten(), cone_z.flatten()]))
cone_x_rot = cone_xyz[0].reshape(cone_x.shape) + st_x
cone_y_rot = cone_xyz[1].reshape(cone_y.shape) + st_y
cone_z_rot = cone_xyz[2].reshape(cone_z.shape) + st_z

coverage_trace = go.Surface(
    x=cone_x_rot, y=cone_y_rot, z=cone_z_rot,
    colorscale='Blues', opacity=0.2, showscale=False,
    name='Зона покрытия'
)

# Траектория спутников (упрощенно — круг на высоте 550 км)
orbit_r = R_earth + 550
angles = np.linspace(0, 2 * np.pi, 100)
orbit_x = orbit_r * np.cos(angles)
orbit_y = orbit_r * np.sin(angles)
orbit_z = np.zeros_like(angles)  # Плоская орбита для простоты

orbit_trace = go.Scatter3d(
    x=orbit_x, y=orbit_y, z=orbit_z,
    mode='lines', line=dict(color='gray', width=2, dash='dash'),
    name='Орбита'
)

# ==========================================
# 3. АНИМАЦИЯ (КАДРЫ)
# ==========================================
frames = []
num_frames = 60
collected_shares = 6  # Начинаем с 6 из 8
max_shares = 8

for i in range(num_frames):
    t = i / num_frames * 2 * np.pi  # Время (угол по орбите)

    # Текущий спутник (один для примера)
    sat_x = orbit_r * np.cos(t)
    sat_y = orbit_r * np.sin(t)
    sat_z = 0

    # Формируем кадр
    frame = go.Frame(
        data=[
            earth_trace,
            coverage_trace,
            orbit_trace,
            # Спутник
            go.Scatter3d(x=[sat_x], y=[sat_y], z=[sat_z],
                         mode='markers', marker=dict(size=8, color='red'),
                         name='Спутник'),
            # Линк атаки (от спутника к станции)
            go.Scatter3d(x=[sat_x, st_x], y=[sat_y, st_y], z=[sat_z, st_z],
                         mode='lines', line=dict(color='red', width=3, dash='dot'),
                         name='Атака (перехват)'),
            # Наземная станция
            go.Scatter3d(x=[st_x], y=[st_y], z=[st_z],
                         mode='markers', marker=dict(size=10, color='gold', symbol='diamond'),
                         name='Станция')
        ],
        name=f'frame_{i}'
    )
    frames.append(frame)

# ==========================================
# 4. СБОРКА ГРАФИКА
# ==========================================
fig = go.Figure(
    data=[
        earth_trace,
        coverage_trace,
        orbit_trace,
        # Начальное состояние
        go.Scatter3d(x=[orbit_x[0]], y=[orbit_y[0]], z=[0],
                     mode='markers', marker=dict(size=8, color='red'), name='Спутник'),
        go.Scatter3d(x=[orbit_x[0], st_x], y=[orbit_y[0], st_y], z=[0, st_z],
                     mode='lines', line=dict(color='red', width=3, dash='dot'), name='Атака'),
        go.Scatter3d(x=[st_x], y=[st_y], z=[st_z],
                     mode='markers', marker=dict(size=10, color='gold', symbol='diamond'), name='Станция')
    ],
    frames=frames
)

# Настройки сцены
fig.update_layout(
    title='LEO: 3D Симуляция атаки на сбор ключа (Земля + Зона покрытия)',
    scene=dict(
        xaxis=dict(title='X (км)', range=[-8000, 8000]),
        yaxis=dict(title='Y (км)', range=[-8000, 8000]),
        zaxis=dict(title='Z (км)', range=[-8000, 8000]),
        aspectmode='cube',  # Сохраняем пропорции сферы
        bgcolor='black'
    ),
    updatemenus=[dict(
        type='buttons',
        buttons=[dict(label='▶ Запустить симуляцию', method='animate',
                      args=[None, dict(frame=dict(duration=100, redraw=True), fromcurrent=True)])]
    )],
    legend=dict(x=0, y=1)
)

# Добавляем динамический текст статуса (пока статичный, но можно обновлять через аннотации)
fig.add_annotation(
    text="t=0 мин | собрано=6/8 | атака/недостаточно",
    x=0.05, y=0.95, xref='paper', yref='paper',
    showarrow=False, font=dict(color='red', size=14)
)

fig.show()