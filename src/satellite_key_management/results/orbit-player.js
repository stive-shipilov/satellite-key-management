(() => {
    "use strict";

    const byId = id => document.getElementById(id);
    const data = JSON.parse(byId("orbit-data").textContent);
    const canvas = byId("orbit-canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) {
        byId("orbit-error").hidden = false;
        return;
    }
    const isContact = data.mode === "contact";
    const isVisibility = data.mode !== "schemes";
    let contactProfile = data.contact_presets?.short;
    let contactRun;
    const radius = OrbitScenario.radius;
    let config = data.config;
    let observer = data.observer;
    let geometry = OrbitScenario.createGeometry(config, observer);
    const comparisonMembers = new Set(isVisibility ? [] : geometry.ids.slice(0, data.members));
    let events = [];
    let history, summary, chartMax, lastMinute;
    let visible, observed, exposures, isolated;
    const color = {
        quiet: "#758ca6", visible: "#6fdbff", observed: "#c5a5ff",
        both: "#8bf2c8", exposure: "#ffbe78", isolated: "#ef90a0", station: "#fff2da", observer: "#c5a5ff",
    };
    const groupColors = ["#82b4ee", "#7adfc0", "#edb4e6"];
    const viewNames = {
        quiet: "Вне зоны", visible: "Станция связи", observed: "Зона наблюдения",
        both: "Обе зоны", exposure: "Доля раскрыта", isolated: "Изолирован",
    };
    const sceneSize = { width: 0, height: 0, scale: 1 };
    const textureMap = document.createElement("canvas");
    const globe = document.createElement("canvas");
    const earth = globe.getContext("2d");
    const backdrop = document.createElement("canvas");
    const background = backdrop.getContext("2d");
    const satelliteLabel = byId("satellite-label");
    const playButton = byId("orbit-play");
    const seek = byId("orbit-seek");
    const clock = byId("orbit-time");
    const number = new Intl.NumberFormat("ru", { maximumFractionDigits: 1 });
    const elevation = vector => Math.atan2(vector[2], Math.hypot(vector[0], vector[1]));
    const wrap = (value, period) => (value % period + period) % period;
    const limit = (value, min, max) => Math.max(min, Math.min(max, value));
    let yaw, pitch, zoom, camera;
    let texture = null;
    let globeDirty = true;
    let drag = null;
    let dots = [];
    let time = 0;
    let previous = null;
    let playing = false;
    let speed = 1;
    let request = 0;
    let shownMinute = -1;
    const stats = byId("orbit-metrics");

    function drawSoon() {
        if (!request) request = requestAnimationFrame(draw);
    }

    function changeCamera() {
        camera = {
            sinYaw: Math.sin(yaw), cosYaw: Math.cos(yaw),
            sinPitch: Math.sin(pitch), cosPitch: Math.cos(pitch),
        };
        globeDirty = true;
        drawSoon();
    }

    function centerCamera(point, pitchOffset) {
        yaw = Math.atan2(point[1], point[0]) + .19;
        pitch = limit(elevation(point) + pitchOffset, -1.52, 1.52);
        zoom = 1;
        changeCamera();
    }

    function resetCamera() {
        centerCamera(geometry.stations[0], isVisibility ? -.18 : .22);
    }

    function rotate(x, y, z) {
        const {sinYaw, cosYaw, sinPitch, cosPitch} = camera;
        const forward = cosYaw * x + sinYaw * y;
        return {
            x: -sinYaw * x + cosYaw * y,
            y: cosPitch * z - sinPitch * forward,
            z: cosPitch * forward + sinPitch * z,
        };
    }

    function resize() {
        const {width, height} = canvas.getBoundingClientRect();
        const ratio = Math.min(devicePixelRatio || 1, 2);
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
        backdrop.width = canvas.width;
        backdrop.height = canvas.height;
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        background.setTransform(ratio, 0, 0, ratio, 0, 0);
        Object.assign(sceneSize, {width, height, scale: Math.min(width * .36, height * .365) / radius});
        globeDirty = true;
        drawSoon();
    }

    function renderGlobe(screenRadius) {
        const diameter = Math.max(48, Math.min(600, Math.round(screenRadius * 2 * devicePixelRatio)));
        globe.width = globe.height = diameter;
        const pixels = earth.createImageData(diameter, diameter);
        const {sinYaw, cosYaw, sinPitch, cosPitch} = camera;
        for (let row = 0; row < diameter; row++) {
            const up = 1 - 2 * (row + .5) / diameter;
            for (let column = 0; column < diameter; column++) {
                const right = 2 * (column + .5) / diameter - 1;
                const distance = right * right + up * up;
                if (distance >= 1) continue;
                const front = Math.sqrt(1 - distance);
                const i = (row * diameter + column) * 4;
                const forward = cosPitch * front - sinPitch * up;
                const wx = cosYaw * forward - sinYaw * right;
                const wy = sinYaw * forward + cosYaw * right;
                const wz = limit(sinPitch * front + cosPitch * up, -1, 1);
                const light = .50 + .47 * Math.max(0, .85 * front - .34 * right + .33 * up);
                const haze = .32 * (1 - front) ** 2;
                let r = 29, g = 76, b = 126;
                if (texture) {
                    const x = Math.floor(wrap(.5 + Math.atan2(wy, wx) / (2 * Math.PI), 1) * texture.width);
                    const y = Math.min(texture.height - 1,
                        Math.floor((.5 - Math.asin(wz) / Math.PI) * texture.height));
                    const index = (y * texture.width + x) * 4;
                    r = texture.data[index];
                    g = texture.data[index + 1];
                    b = texture.data[index + 2];
                }
                pixels.data[i] = r * light * (1 - haze) + 113 * haze;
                pixels.data[i + 1] = g * light * (1 - haze) + 185 * haze;
                pixels.data[i + 2] = b * light * (1 - haze) + 15 + 242 * haze;
                pixels.data[i + 3] = 255 * Math.min(1, (1 - distance) * diameter * .22);
            }
        }
        earth.putImageData(pixels, 0, 0);
        globeDirty = false;
    }

    // Distant stars stay in place on screen, while the globe and orbits respond to the camera.
    const stars = Array.from({length: 96}, (_, i) => [
        wrap((i + 1) * .618034, 1), wrap((i + 1) * .414214, 1), i % 9 === 0 ? 1.15 : .55,
    ]);

    function screenPoint(point, scale, cx, cy) {
        return [cx + point.x * scale, cy - point.y * scale];
    }

    function paintBackdrop(width, height, cx, cy, screenRadius) {
        renderGlobe(screenRadius);
        camera.stations = geometry.stations.map(point => rotate(...point));

        background.clearRect(0, 0, width, height);
        background.fillStyle = "#a7c6e67a";
        for (const [x, y, size] of stars) background.fillRect(x * width, y * height, size, size);

        const halo = background.createRadialGradient(cx, cy, screenRadius * .95, cx, cy, screenRadius * 1.10);
        halo.addColorStop(0, "#63afff00");
        halo.addColorStop(.36, "#70c2ff64");
        halo.addColorStop(1, "#63afff00");
        background.fillStyle = halo;
        background.fillRect(cx - screenRadius * 1.1, cy - screenRadius * 1.1, screenRadius * 2.2, screenRadius * 2.2);
        background.drawImage(globe, cx - screenRadius, cy - screenRadius, screenRadius * 2, screenRadius * 2);
    }

    function paintPaths(project, onScreen) {
        const angle = -OrbitScenario.earthRotation * time;
        const cos = Math.cos(angle), sin = Math.sin(angle);
        ctx.lineWidth = 1;
        geometry.shells.forEach(({paths}, index) => {
            ctx.strokeStyle = groupColors[index] + "68";
            ctx.beginPath();
            for (const path of paths) {
                let drawing = false;
                for (const [x, y, z] of path) {
                    const point = rotate(x * cos - y * sin, x * sin + y * cos, z);
                    if (!onScreen(point)) {
                        drawing = false;
                        continue;
                    }
                    if (drawing) ctx.lineTo(...project(point));
                    else ctx.moveTo(...project(point));
                    drawing = true;
                }
            }
            ctx.stroke();
        });
    }

    function paintLinks(origin, links, sourceColor, exposedColor) {
        if (!origin) return;
        for (const [points, stroke, dash] of [
            [links.regular, sourceColor, []],
            [links.exposed, exposedColor, [6, 4]],
        ]) {
            if (!points.length) continue;
            ctx.strokeStyle = stroke;
            ctx.lineWidth = dash.length ? 2 : 1.4;
            ctx.setLineDash(dash);
            ctx.beginPath();
            for (const point of points) {
                ctx.moveTo(...origin);
                ctx.lineTo(...point);
            }
            ctx.stroke();
        }
        ctx.setLineDash([]);
        ctx.lineWidth = 1;
    }

    function paintScene() {
        const {width, height, scale: baseScale} = sceneSize;
        if (!width || !height) return;
        const scale = baseScale * zoom;
        const cx = width / 2, cy = height * .535;
        const screenRadius = radius * scale;
        const project = point => screenPoint(point, scale, cx, cy);
        if (globeDirty) paintBackdrop(width, height, cx, cy, screenRadius);

        ctx.clearRect(0, 0, width, height);
        ctx.drawImage(backdrop, 0, 0, width, height);
        const [station, observerPoint] = camera.stations;
        const stationOrigin = station.z >= 0 ? project(station) : null;
        const observerOrigin = observerPoint?.z >= 0 ? project(observerPoint) : null;
        const stationLinks = {regular: [], exposed: []};
        const observerLinks = {regular: [], exposed: []};
        const onScreen = point => point.z >= 0 || Math.hypot(point.x, point.y) > radius;
        paintPaths(project, onScreen);
        const positions = geometry.positionsAt(time);
        dots = [];
        for (let i = 0; i < positions.length; i++) {
            const sid = geometry.ids[i];
            const point = rotate(...positions[i]);
            if (!onScreen(point)) continue;
            const screen = project(point);
            const [x, y] = screen;
            const stationSees = visible.has(sid), observerSees = observed.has(sid);
            const exposed = exposures.has(sid), unavailable = isolated.has(sid);
            const group = unavailable ? "isolated" : exposed ? "exposure" : stationSees ?
                (observerSees ? "both" : "visible") : (observerSees ? "observed" : "quiet");
            const style = exposed ? "exposed" : "regular";
            if (stationOrigin && stationSees && !unavailable) stationLinks[style].push(screen);
            if (observerOrigin && observerSees) observerLinks[style].push(screen);
            dots.push({x, y, sid, group, z: point.z});
        }
        paintLinks(stationOrigin, stationLinks, "#6fdbffb3", "#ffd49b");
        paintLinks(observerOrigin, observerLinks, "#c5a5ffe0", "#ffb46d");
        dots.sort((a, b) => a.z - b.z);
        for (const dot of dots) {
            const far = dot.z < 0;
            const quiet = dot.group === "quiet";
            const size = quiet ? (far ? 1.55 : 2.15) : 3.65;
            ctx.globalAlpha = far && quiet ? .56 : 1;
            ctx.fillStyle = color[dot.group];
            ctx.beginPath();
            if (dot.group === "exposure" || dot.group === "isolated") {
                ctx.moveTo(dot.x, dot.y - 6);
                ctx.lineTo(dot.x + 6, dot.y);
                ctx.lineTo(dot.x, dot.y + 6);
                ctx.lineTo(dot.x - 6, dot.y);
                ctx.closePath();
            } else ctx.arc(dot.x, dot.y, size, 0, 2 * Math.PI);
            ctx.fill();
        }
        ctx.globalAlpha = 1;
        camera.stations.forEach((point, i) => {
            if (point.z < 0) return;
            const [x, y] = project(point);
            ctx.fillStyle = i ? color.observer : color.station;
            ctx.beginPath();
            ctx.arc(x, y, 5, 0, 2 * Math.PI);
            ctx.fill();
            ctx.strokeStyle = i ? "#c5a5ff66" : "#fff2da77";
            ctx.beginPath();
            ctx.arc(x, y, 9, 0, 2 * Math.PI);
            ctx.stroke();
            ctx.font = "600 12px system-ui";
            ctx.lineWidth = 3;
            ctx.strokeStyle = "#091827";
            const label = i ? "Наблюдатель" : "Станция";
            const labelX = i ? x + 12 : x - ctx.measureText(label).width - 12;
            ctx.strokeText(label, labelX, y - 9);
            ctx.fillText(label, labelX, y - 9);
            ctx.lineWidth = 1;
        });
    }

    function drawTracks(minute) {
        const chart = byId("shares-chart");
        const width = Math.round(chart.getBoundingClientRect().width);
        const height = 186;
        const ratio = Math.min(devicePixelRatio || 1, 2);
        const pixelWidth = Math.round(width * ratio);
        if (chart.width !== pixelWidth || chart.height !== height * ratio) {
            chart.width = pixelWidth;
            chart.height = height * ratio;
        }
        const plot = chart.getContext("2d");
        plot.setTransform(ratio, 0, 0, ratio, 0, 0);
        plot.clearRect(0, 0, width, height);
        const x = t => 30 + t / history.length * (width - 49);
        const lane = (top, label, getCount, stroke) => {
            const bottom = top + 52;
            const y = count => bottom - count / chartMax * 45;
            plot.font = "12px system-ui";
            plot.fillStyle = stroke;
            plot.fillText(label, 1, top - 5);
            plot.font = "10px system-ui";
            plot.fillStyle = "#a8bfd5";
            plot.fillText(String(chartMax), 1, y(chartMax) + 3);
            plot.fillText("0", 1, y(0) + 3);
            for (const [t, row] of history.entries()) {
                if (!row.exposedKey || top < 90) continue;
                plot.fillStyle = "#ffbe7821";
                plot.fillRect(x(t), y(chartMax), x(t + 1) - x(t), y(0) - y(chartMax));
            }
            for (const [event, marker] of [["refreshed", "#7590ab6c"], ["rotated", "#c5a5ff"]]) {
                plot.strokeStyle = marker;
                plot.beginPath();
                for (const [t, row] of history.entries()) {
                    if (!row[event]) continue;
                    plot.moveTo(x(t), y(chartMax));
                    plot.lineTo(x(t), y(0));
                }
                plot.stroke();
            }
            plot.strokeStyle = "#455d77";
            plot.beginPath();
            plot.moveTo(x(0), y(0));
            plot.lineTo(x(history.length), y(0));
            plot.stroke();
            plot.setLineDash([4, 4]);
            plot.strokeStyle = "#b3c5d7";
            plot.beginPath();
            plot.moveTo(x(0), y(config.k));
            plot.lineTo(x(history.length), y(config.k));
            plot.stroke();
            plot.setLineDash([]);
            plot.fillStyle = "#d3dfec";
            plot.fillText("k", x(history.length) + 5, y(config.k) + 3);
            plot.beginPath();
            plot.moveTo(x(0), y(getCount(history[0])));
            for (let t = 0; t < history.length; t++) {
                if (t) plot.lineTo(x(t), y(getCount(history[t])));
                plot.lineTo(x(t + 1), y(getCount(history[t])));
            }
            plot.strokeStyle = stroke;
            plot.stroke();
            plot.strokeStyle = "#e2eaffb0";
            plot.beginPath();
            plot.moveTo(x(minute), top);
            plot.lineTo(x(minute), bottom);
            plot.stroke();
            plot.fillStyle = stroke;
            plot.beginPath();
            plot.arc(x(minute), y(getCount(history[minute])), 3, 0, Math.PI * 2);
            plot.fill();
        };
        lane(25, "Получено станцией", row => row.received.length, color.visible);
        lane(108, "Раскрытые доли", row => row.exposed.length, color.exposure);
        plot.fillStyle = "#a8bfd5";
        plot.font = "11px system-ui";
        plot.fillText("0", x(0), 181);
        if (lastMinute) plot.fillText(`${lastMinute} мин`, width - 49, 181);
    }

    function updateMinute(minute) {
        const row = history[minute];
        visible = new Set(row.visible);
        observed = new Set(row.observed);
        exposures = new Set(row.exposed);
        isolated = new Set(row.isolated);
        clock.textContent = `${minute} / ${lastMinute} мин`;
        seek.value = minute;
        byId("observed-count").textContent = observed.size;
        if (isVisibility) {
            byId("visible-count").textContent = `${row.received.length} / ${config.k}`;
            byId("epoch").textContent = `${row.session} / ${row.epoch}`;
            byId("share-count").textContent = `${row.exposed.length} / ${config.k}`;
            const reception = byId("station-status");
            reception.classList.toggle("waiting", !row.ready);
            reception.textContent = row.ready ? "Кворум доступен" : "Ожидание кворума";
            const status = byId("key-status");
            status.classList.toggle("exposed", row.exposedKey);
            status.textContent = row.exposedKey ? "Ключ раскрыт в модели" : "Признаков раскрытия ключа в модели нет";
            const now = byId("exposure-now");
            now.textContent = [
                row.rotated ? "Новый ключ" : row.refreshed ? "Обновлены доли" : "",
                row.disclosed.length ? `Новые раскрытия: № ${row.disclosed.join(", ")}` : "",
                row.disclosedKey ? "Раскрытие ключа целиком" : "",
            ].filter(Boolean).join(" · ");
            now.hidden = !isContact && !now.textContent;
            if (isContact) now.title = now.textContent;
            drawTracks(minute);
            if (isContact) showContactProgress(minute);
        } else {
            byId("visible-count").textContent = visible.size;
            const count = row.visible.filter(sid => comparisonMembers.has(sid)).length;
            for (const [i, scheme] of data.schemes.entries()) {
                const success = count >= scheme.threshold;
                const state = byId(`state-${i}`);
                const bar = byId(`bar-${i}`);
                state.textContent = `${count}/${scheme.threshold} · ${success ? "Кворум доступен" : "Ожидает доли"}`;
                state.classList.toggle("ready", success);
                bar.classList.toggle("ready", success);
                bar.style.width = `${Math.min(100, count / scheme.threshold * 100)}%`;
            }
        }
    }

    function draw(timestamp) {
        request = 0;
        if (playing && previous !== null) time = Math.min(lastMinute, time + (timestamp - previous) * speed / 380);
        previous = playing ? timestamp : null;
        const minute = Math.floor(time);
        if (minute !== shownMinute) {
            shownMinute = minute;
            updateMinute(minute);
        }
        paintScene();
        if (playing && time >= lastMinute) setPlaying(false);
        if (playing) drawSoon();
    }

    function setPlaying(value) {
        playing = value;
        previous = null;
        playButton.textContent = playing ? "Ⅱ Пауза" : "▶ Пуск";
        if (playing) drawSoon();
    }

    function seekTime(minute) {
        setPlaying(false);
        time = minute;
        satelliteLabel.hidden = true;
        drawSoon();
    }

    const legendMark = (group, label, diamond = false) =>
        `<span><i class="${diamond ? "diamond" : ""}" style="--mark:${color[group]}"></i>${label}</span>`;
    const linkMark = (mark, label, dashed = false) =>
        `<span><i class="line-mark${dashed ? " dashed" : ""}" style="--mark:${mark}"></i>${label}</span>`;

    function updateObserverLabels() {
        const marks = [legendMark("visible", "Видны станции")];
        if (observer) marks.push(legendMark("observed", "Видны наблюдателю"), legendMark("both", "Видны обеим точкам"));
        if (isVisibility) marks.push(legendMark("exposure", "Доля раскрыта", true), legendMark("isolated", "Изолирован", true));
        marks.push(legendMark("quiet", "Вне зоны"));
        byId("orbit-legend").innerHTML = marks.join("");
        const links = [linkMark(color.visible, "Связь со станцией")];
        if (observer) links.push(linkMark(color.observed, "Радиовидимость наблюдателя"));
        if (isVisibility) links.push(linkMark(color.exposure, "Доля спутника раскрыта", true));
        byId("orbit-link-legend").innerHTML = links.join("");
        byId("observed-count").parentElement.hidden = !observer;
        byId("show-observer").disabled = !observer;
        const formatCoordinate = new Intl.NumberFormat("ru", {maximumFractionDigits: 6});
        const coordinate = (value, positive, negative) =>
            `${formatCoordinate.format(Math.abs(value))}°${value ? " " + (value > 0 ? positive : negative) : ""}`;
        byId("observer-position").textContent = observer ?
            `${coordinate(observer.lat, "с. ш.", "ю. ш.")}, ${coordinate(observer.lon, "в. д.", "з. д.")}. Угол места от ${number.format(config.mask)}°.` :
            "Наблюдатель скрыт.";
    }

    const stat = (label, id) => `<div><dt>${label}</dt><dd id="${id}">0</dd></div>`;
    const observedStat = stat("Видно наблюдателю", "observed-count");
    if (isVisibility) {
        stats.innerHTML = `<dl class="orbit-stat-list">
          ${stat("Доли у станции", "visible-count")}${stat("Доли у нарушителя", "share-count")}
          ${stat("Сеанс / эпоха", "epoch")}${observedStat}</dl>
          <div class="orbit-state-pair"><p id="station-status" class="orbit-status"></p>
          <p id="key-status" class="orbit-status"></p></div>
          <p id="exposure-now" class="orbit-note" hidden></p>
          <dl class="orbit-summary" id="scenario-summary"></dl>
          ${isContact ? '<section class="contact-progress"><h3 id="contact-progress-heading">Контакты наблюдателя</h3><ul id="contact-progress" tabindex="0" aria-labelledby="contact-progress-heading"></ul></section>' : ''}`;
        const tracks = document.createElement("figure");
        tracks.className = "orbit-tracks";
        tracks.innerHTML = `<figcaption>Пунктир — порог. Серые вертикали — обновление долей, сиреневые — смена ключа. Оранжевый фон — ключ раскрыт.</figcaption>
          <canvas id="shares-chart" role="img" aria-label="Доли у станции и нарушителя по минутам"></canvas>`;
        document.querySelector(".orbit-timeline").append(tracks);
    } else {
        const visibleStat = stat("Видно станции", "visible-count");
        stats.innerHTML = `<dl class="orbit-stat-list">${visibleStat}${observedStat}</dl>
          <ul class="scheme-list" id="scheme-list"></ul>`;
        const list = byId("scheme-list");
        data.schemes.forEach((scheme, i) => {
            const item = document.createElement("li");
            item.innerHTML = `<strong></strong><span class="scheme-state" id="state-${i}"></span>
              <span class="scheme-progress" aria-hidden="true"><span id="bar-${i}"></span></span>
              <small class="scheme-meta"></small>`;
            item.querySelector("strong").textContent = scheme.name;
            item.querySelector("small").textContent = [
                scheme.size === null ? null : `Доля ${number.format(scheme.size)} Б`,
                scheme.recover_us === null ? null : `Восстановление ${number.format(scheme.recover_us)} мкс`,
            ].filter(Boolean).join(" · ");
            list.append(item);
        });
        if (!list.children.length) list.textContent = "Для этих параметров схемы недоступны.";
    }

    function recompute() {
        if (isContact) {
            contactRun = OrbitScenario.contactRisk(config, geometry.contacts, contactProfile);
            renderContactLog();
        }
        ({history, summary} = OrbitScenario.run(config, geometry.contacts, isContact ? contactRun.events : events));
        lastMinute = history.length - 1;
        chartMax = history.reduce((max, row) => Math.max(max, row.received.length, row.exposed.length), config.k);
        shownMinute = -1;
        satelliteLabel.hidden = true;
        seek.max = lastMinute;
        seek.disabled = playButton.disabled = lastMinute === 0;
        byId("orbit-duration").textContent = `${lastMinute} мин`;
        const groups = OrbitScenario.groupsFor(config);
        const totalPlanes = groups.reduce((count, group) => count + group.planes, 0);
        const drawnPlanes = geometry.shells.reduce((count, shell) => count + shell.paths.length, 0);
        const drawn = drawnPlanes < totalPlanes ? ` · показано плоскостей ${drawnPlanes}` : "";
        byId("constellation").textContent = `${geometry.ids.length} спутн. · ${totalPlanes} плоск. · ${groups.length} гр.${drawn}`;
        byId("orbit-group-legend").innerHTML = groups.map(({inclination, altitude, n}, i) =>
            linkMark(groupColors[i], `Группа ${i + 1}: ${n} спутн., ${number.format(inclination)}°, ${number.format(altitude)} км`)
        ).join("");
        updateObserverLabels();
        if (isVisibility) {
            const availablePercent = number.format(100 * summary.available / history.length);
            byId("scenario-summary").innerHTML = `<div><dt>Окна с кворумом</dt>
              <dd>${availablePercent}% · ${summary.available} из ${history.length} мин</dd></div>
              <div><dt>Макс. простой</dt><dd>${summary.longest} мин</dd></div>
              <div><dt>Первое раскрытие ключа</dt><dd>${summary.first === null ? "—" : summary.first + " мин"}</dd></div>
              <div><dt>Время с раскрытым ключом</dt><dd>${summary.exposedMinutes} мин</dd></div>`;
        }
        seekTime(Math.min(Math.floor(time), lastMinute));
    }

    function enableOrbitControls(onChange) {
        const configForm = byId("scenario-config");
        const field = name => configForm.elements.namedItem(name);
        const groupCount = field("group-count");
        const groupContainer = byId("orbit-groups");
        const template = byId("orbit-group-template");
        const groupEditors = data.group_presets.map((_, index) => {
            const editor = template.content.firstElementChild.cloneNode(true);
            const heading = editor.querySelector("legend");
            heading.textContent = `Группа ${index + 1}`;
            heading.style.setProperty("--orbit-accent", groupColors[index]);
            groupContainer.append(editor);
            return editor;
        });

        function readGroups() {
            return groupEditors.slice(0, Number(groupCount.value)).map(editor =>
                Object.fromEntries([...editor.querySelectorAll("[data-field]")].map(input =>
                    [input.dataset.field, input.valueAsNumber])));
        }

        function updateBounds() {
            const groups = readGroups();
            for (const [i, editor] of groupEditors.entries()) {
                editor.hidden = editor.disabled = i >= groups.length;
                const count = groups[i]?.n;
                editor.querySelector('[data-field="planes"]').max = Number.isFinite(count) ? count : "";
            }
            const total = groups.reduce((sum, group) => sum + (group.n || 0), 0);
            field("k").max = total;
            groupCount.setCustomValidity(total > 256 ? "Во всех группах суммарно может быть до 256 спутников." : "");
        }

        function showPeriods() {
            geometry.shells.forEach(({period}, i) => {
                groupEditors[i].querySelector(".group-period").textContent = `Период витка ${number.format(period)} мин`;
            });
        }

        const fields = ["k", "refresh", "rotation", "lat", "lon", "mask", "minutes"];
        function syncConfig() {
            const groups = OrbitScenario.groupsFor(config);
            groupCount.value = String(groups.length);
            groupEditors.forEach((editor, i) => {
                for (const [name, value] of Object.entries(groups[i] ?? data.group_presets[i])) {
                    editor.querySelector(`[data-field="${name}"]`).value = value;
                }
            });
            for (const name of fields) field(name).value = config[name];
            updateBounds();
            showPeriods();
        }
        field("minutes").max = Math.max(1440, config.minutes);
        configForm.addEventListener("input", updateBounds);
        configForm.addEventListener("submit", event => {
            event.preventDefault();
            const parameters = Object.fromEntries(fields.map(name => [name, field(name).valueAsNumber]));
            config = {...parameters, groups: readGroups()};
            geometry = OrbitScenario.createGeometry(config, observer);
            resetCamera();
            recompute();
            onChange?.();
            showPeriods();
            byId("config-message").textContent = "Прогон пересчитан.";
        });
        syncConfig();
        return syncConfig;
    }

    function enableManualEvents() {
        const eventForm = byId("scenario-event");
        const eventField = name => eventForm.elements.namedItem(name);
        const log = byId("event-log");
        const kind = eventField("kind");
        const eventMinute = eventField("minute");
        const sid = eventField("sid");
        const eventMessage = byId("event-message");
        let edited = null;
        const labels = Object.fromEntries([...kind.options].map(option => [option.value, option.text]));
        const needsNode = type => type !== "rotate" && type !== "key";
        const active = event => event.minute <= lastMinute && (!event.sid || geometry.ids.includes(event.sid));

        function updateSatelliteOptions() {
            const previous = sid.value;
            sid.replaceChildren();
            const placeholder = new Option("Выберите спутник", "");
            placeholder.disabled = true;
            sid.add(placeholder);
            const groups = OrbitScenario.groupsFor(config);
            let next = 0;
            for (const [i, group] of groups.entries()) {
                const options = document.createElement("optgroup");
                options.label = `Группа ${i + 1}`;
                for (const id of geometry.ids.slice(next, next + group.n)) options.append(new Option(`№ ${id}`, id));
                sid.append(options);
                next += group.n;
            }
            sid.value = geometry.ids.includes(Number(previous)) ? previous : String(geometry.ids[0]);
        }

        function updateEventKind() {
            const node = needsNode(kind.value);
            byId("event-node").hidden = !node;
            sid.required = node;
            sid.disabled = !node;
        }

        function endEdit() {
            edited = null;
            byId("save-event").textContent = "Добавить событие";
            byId("cancel-event").hidden = true;
        }

        function logButton(label, action, accessibleName = label) {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = label;
            button.setAttribute("aria-label", accessibleName);
            button.addEventListener("click", action);
            return button;
        }

        function renderLog() {
            log.replaceChildren();
            if (!events.length) {
                const empty = document.createElement("li");
                empty.textContent = "Событий пока нет.";
                log.append(empty);
            }
            for (const event of [...events].sort((a, b) => a.minute - b.minute)) {
                const row = document.createElement("li");
                const minute = logButton(`${event.minute} мин`, () => seekTime(event.minute));
                minute.disabled = !active(event);
                const caption = document.createElement("span");
                caption.textContent = labels[event.kind] + (event.sid ? ` · № ${event.sid}` : "") +
                    (active(event) ? "" : " · вне прогона");
                const edit = logButton("Править", () => {
                    edited = event;
                    kind.value = event.kind;
                    eventMinute.value = event.minute;
                    sid.value = geometry.ids.includes(event.sid) ? String(event.sid) : "";
                    updateEventKind();
                    byId("save-event").textContent = "Сохранить событие";
                    byId("cancel-event").hidden = false;
                    eventMinute.focus();
                }, `Править событие на ${event.minute}-й минуте`);
                const remove = logButton("Удалить", () => {
                    events = events.filter(item => item !== event);
                    if (edited === event) endEdit();
                    eventMessage.textContent = "Событие удалено.";
                    refreshLog();
                }, `Удалить событие на ${event.minute}-й минуте`);
                row.append(minute, caption, edit, remove);
                log.append(row);
            }
        }

        function refreshLog() {
            recompute();
            renderLog();
        }

        eventMinute.value = 0;
        kind.addEventListener("change", updateEventKind);
        byId("event-now").addEventListener("click", () => { eventMinute.value = Math.floor(time); });
        byId("cancel-event").addEventListener("click", () => {
            endEdit();
            eventMessage.textContent = "";
        });
        eventForm.addEventListener("submit", event => {
            event.preventDefault();
            const entry = {minute: eventMinute.valueAsNumber, kind: kind.value};
            if (needsNode(entry.kind)) entry.sid = Number(sid.value);
            if (events.some(item => item !== edited && item.minute === entry.minute &&
                item.kind === entry.kind && item.sid === entry.sid)) {
                eventMessage.textContent = "Такое событие уже есть.";
                return;
            }
            if (edited) events[events.indexOf(edited)] = entry;
            else events.push(entry);
            endEdit();
            refreshLog();
            seekTime(entry.minute);
            eventMessage.textContent = "Событие сохранено. Шкала перемотана к его минуте.";
        });
        for (const button of document.querySelectorAll("[data-example]")) {
            button.addEventListener("click", () => {
                const name = button.dataset.example;
                events = name === "empty" ? [] : OrbitScenario.example(config, name);
                endEdit();
                refreshLog();
                const target = name === "empty" ? 0 : events.at(-1)?.minute ?? 0;
                seekTime(target);
                eventMessage.textContent = name === "empty" ? "События очищены." : "Пример загружен.";
            });
        }
        updateEventKind();
        function syncEvents() {
            eventMinute.max = lastMinute;
            updateSatelliteOptions();
            renderLog();
        }
        syncEvents();
        return syncEvents;
    }

    const contactLabels = {
        waiting: "Идёт отсчёт", revealed: "Доля раскрыта", known: "Доля уже раскрыта",
        failed: "Доля не раскрылась", interrupted: "Контакт прерван", refreshed: "Сменилась эпоха",
        rotated: "Сменился ключ",
    };

    function showContactProgress(minute) {
        const list = byId("contact-progress");
        const scrollTop = list.scrollTop;
        list.replaceChildren();
        const rows = contactRun.progress[minute];
        if (!rows.length) {
            const li = document.createElement("li");
            li.textContent = "Спутников в зоне наблюдения нет.";
            list.append(li);
        }
        for (const {sid, elapsed, status} of rows) {
            const li = document.createElement("li");
            const label = document.createElement("span");
            label.textContent = `№ ${sid} · ${contactLabels[status]}`;
            if (status === "revealed" || status === "known") label.className = "contact-disclosed";
            li.append(label);
            if (status === "waiting") {
                const progress = document.createElement("progress");
                progress.max = contactProfile.duration;
                progress.value = elapsed;
                progress.setAttribute("aria-label", `№ ${sid}, ${elapsed} из ${contactProfile.duration} мин`);
                const duration = document.createElement("small");
                duration.textContent = `${elapsed} / ${contactProfile.duration} мин`;
                li.append(progress, duration);
            }
            list.append(li);
        }
        list.scrollTop = scrollTop;
    }

    function renderContactLog() {
        const log = byId("contact-log");
        const entries = contactRun.log;
        log.replaceChildren();
        if (!entries.length) {
            const empty = document.createElement("li");
            empty.textContent = "За этот прогон нет завершённых проверок или прерванных контактов.";
            log.append(empty);
            return;
        }
        for (const {minute, sid, elapsed, status} of entries) {
            const row = document.createElement("li");
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = `${minute} мин`;
            button.addEventListener("click", () => seekTime(minute));
            const caption = document.createElement("span");
            caption.textContent = `№ ${sid} · ${contactLabels[status]} · контакт ${elapsed} мин`;
            if (status === "revealed") caption.className = "contact-disclosed";
            row.append(button, caption);
            log.append(row);
        }
    }

    function enableContactControls(syncConfig, syncObserver) {
        const form = byId("contact-form");
        const field = name => form.elements.namedItem(name);
        const message = byId("contact-message");
        function fillProfile() {
            field("duration").value = contactProfile.duration;
            field("probability").value = contactProfile.probability * 100;
            field("seed").value = contactProfile.seed;
        }
        fillProfile();
        form.addEventListener("submit", event => {
            event.preventDefault();
            contactProfile = {duration: field("duration").valueAsNumber, seed: field("seed").valueAsNumber,
                probability: field("probability").valueAsNumber / 100};
            recompute();
            message.textContent = "Окна и исходы пересчитаны.";
        });
        for (const button of document.querySelectorAll("[data-contact-example]")) {
            button.addEventListener("click", () => {
                contactProfile = data.contact_presets[button.dataset.contactExample];
                config = data.config;
                observer = data.observer;
                geometry = OrbitScenario.createGeometry(config, observer);
                resetCamera();
                recompute();
                syncConfig();
                syncObserver();
                fillProfile();
                const target = summary.first ?? lastMinute;
                seekTime(target);
                message.textContent = summary.first === null ? "Ключ остался защищён на всей трассе." :
                    `Кворум раскрытых долей достигнут на ${summary.first}-й минуте.`;
            });
        }
    }

    function enableObserverControls() {
        const form = byId("observer-form");
        const enabled = form.elements.namedItem("enabled");
        const lat = form.elements.namedItem("lat");
        const lon = form.elements.namedItem("lon");
        function syncObserver() {
            enabled.checked = Boolean(observer);
            const point = observer ?? data.observer;
            lat.value = point.lat;
            lon.value = point.lon;
        }
        syncObserver();
        form.addEventListener("submit", event => {
            event.preventDefault();
            observer = enabled.checked ? {lat: lat.valueAsNumber, lon: lon.valueAsNumber} : null;
            geometry = OrbitScenario.createGeometry(config, observer);
            globeDirty = true;
            recompute();
            byId("observer-message").textContent = observer ? "Радиовидимость пересчитана." : "Наблюдатель выключен.";
        });
        byId("show-observer").addEventListener("click", () => {
            centerCamera(geometry.stations[1], .1);
            canvas.scrollIntoView({block: "center"});
            canvas.focus({preventScroll: true});
        });
        return syncObserver;
    }

    if (data.mode === "visibility") events = OrbitScenario.example(config, "below");
    recompute();
    const syncObserver = enableObserverControls();
    if (isVisibility) {
        const syncEvents = isContact ? null : enableManualEvents();
        const syncConfig = enableOrbitControls(syncEvents);
        if (isContact) enableContactControls(syncConfig, syncObserver);
    }

    playButton.addEventListener("click", () => {
        if (!playing && time >= lastMinute) time = 0;
        setPlaying(!playing);
    });
    seek.addEventListener("input", () => seekTime(Number(seek.value)));
    byId("orbit-speed").addEventListener("change", event => { speed = Number(event.target.value); });
    byId("reset-view").addEventListener("click", resetCamera);
    document.addEventListener("visibilitychange", () => { if (document.hidden) setPlaying(false); });

    canvas.addEventListener("pointerdown", event => {
        if (!event.isPrimary || event.button !== 0) return;
        canvas.setPointerCapture(event.pointerId);
        drag = {x: event.clientX, y: event.clientY};
        satelliteLabel.hidden = true;
    });
    canvas.addEventListener("pointermove", event => {
        if (drag && canvas.hasPointerCapture(event.pointerId)) {
            yaw -= (event.clientX - drag.x) * .009;
            pitch = limit(pitch + (event.clientY - drag.y) * .009, -1.52, 1.52);
            drag = {x: event.clientX, y: event.clientY};
            changeCamera();
            return;
        }
        const {left, top} = canvas.getBoundingClientRect();
        const x = event.clientX - left, y = event.clientY - top;
        let hit;
        for (let i = dots.length - 1; i >= 0; i--) {
            if (Math.hypot(dots[i].x - x, dots[i].y - y) <= 7) {
                hit = dots[i];
                break;
            }
        }
        satelliteLabel.hidden = !hit;
        if (hit) satelliteLabel.textContent =
            `Спутник № ${hit.sid} · Группа ${Math.floor((hit.sid - 1) / 1000) + 1} · ${viewNames[hit.group]}`;
    });
    canvas.addEventListener("lostpointercapture", () => { drag = null; });
    canvas.addEventListener("pointerleave", () => { satelliteLabel.hidden = true; });
    canvas.addEventListener("wheel", event => {
        event.preventDefault();
        zoom = limit(zoom * Math.exp(-event.deltaY * .001), .67, 2.3);
        changeCamera();
    }, {passive: false});
    canvas.addEventListener("keydown", event => {
        switch (event.key) {
            case "ArrowLeft": yaw -= .11; break;
            case "ArrowRight": yaw += .11; break;
            case "ArrowUp": pitch = limit(pitch + .11, -1.52, 1.52); break;
            case "ArrowDown": pitch = limit(pitch - .11, -1.52, 1.52); break;
            case "+": case "=": zoom = Math.min(2.3, zoom * 1.12); break;
            case "-": zoom = Math.max(.67, zoom / 1.12); break;
            default: return;
        }
        event.preventDefault();
        changeCamera();
    });

    resetCamera();
    const resizeObserver = new ResizeObserver(() => {
        resize();
        if (isVisibility && shownMinute >= 0) drawTracks(shownMinute);
    });
    resizeObserver.observe(canvas);
    if (data.texture) {
        const image = new Image();
        image.onload = () => {
            textureMap.width = image.width;
            textureMap.height = image.height;
            const source = textureMap.getContext("2d");
            source.drawImage(image, 0, 0);
            texture = source.getImageData(0, 0, image.width, image.height);
            globeDirty = true;
            drawSoon();
        };
        image.src = data.texture;
    }
})();
