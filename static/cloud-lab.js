"use strict";
const $ = (id) => document.getElementById(id),
  canvas = $("space"),
  ctx = canvas.getContext("2d");
const AU = 149597870700,
  DAY = 86400,
  YEAR = 365.25,
  colors = ["#ffd493", "#f4a5d8", "#9dbfff", "#e7cbff", "#f8b69c"];
let worker = null,
  ready = false,
  playing = false,
  advancing = false,
  world = null,
  previous = null,
  receivedAt = 0,
  blendMs = 50,
  requestId = 0;
let yaw = -0.5,
  tilt = 0.55,
  zoom = 1,
  selected = -1,
  inspecting = false,
  points = [],
  W = 0,
  H = 0,
  scale = 1,
  displayTime = 0,
  lastTick = performance.now(),
  credit = 0;
let rates = [],
  actual = 0,
  lastPaint = 0,
  lastSaved = 0,
  saving = false,
  saveAgain = false,
  storageOK = true,
  db = null,
  previousRecord = null,
  saveTimer = 0;
let packetTrails = new Map(),
  cloudHistory = [],
  packetButtons = [],
  lastPacketCount = -1,
  pending = new Map(),
  initialCandidate = null;
const controls = ["offset", "az", "el", "roll"];
const sprites = new Map();
function sprite(color, size = 36) {
  const key = color + size;
  if (sprites.has(key)) return sprites.get(key);
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d"),
    r = size / 2,
    a = g.createRadialGradient(r, r, 0, r, r, r);
  a.addColorStop(0, color);
  a.addColorStop(0.16, color + "ee");
  a.addColorStop(0.35, color + "66");
  a.addColorStop(1, color + "00");
  g.fillStyle = a;
  g.fillRect(0, 0, size, size);
  sprites.set(key, c);
  return c;
}
let starSeed = 127935;
const stars = Array.from({ length: 160 }, () => {
  starSeed = (Math.imul(starSeed, 1664525) + 1013904223) >>> 0;
  const x = starSeed / 4294967296;
  starSeed = (Math.imul(starSeed, 1664525) + 1013904223) >>> 0;
  return [x, starSeed / 4294967296];
});
function fmt(n, d = 2) {
  return Number.isFinite(n)
    ? n.toLocaleString(undefined, { maximumFractionDigits: d })
    : "unbounded";
}
function sci(n) {
  return Math.abs(n) < 0.01 && n !== 0
    ? n.toExponential(2)
    : Math.abs(n) >= 1e6
      ? n.toExponential(2)
      : fmt(n, 2);
}
function rateText(days) {
  return days >= YEAR * 0.1
    ? fmt(days / YEAR, 2) + " years / s"
    : days >= 1
      ? fmt(days, 1) + " days / s"
      : fmt(days * 24, 1) + " hours / s";
}
function values() {
  return {
    speed: +$("speedNumber").value,
    offset: +$("offset").value,
    az: +$("az").value,
    el: +$("el").value,
    roll: +$("roll").value,
  };
}
function labels() {
  for (const id of controls)
    $(id + "Value").textContent =
      fmt(+$(id).value, 1) + (id === "offset" ? " AU" : "°");
}
controls.forEach((id) => $(id).addEventListener("input", labels));
$("speed").oninput = () => {
  $("speedNumber").value = Math.round(
    5 * Math.pow(600, +$("speed").value / 1000),
  );
};
$("speedNumber").oninput = () => {
  $("speed").value =
    (1000 * Math.log(Math.max(5, +$("speedNumber").value) / 5)) / Math.log(600);
};
$("speedNumber").oninput();
function notice(message) {
  $("notice").textContent = message;
  $("notice").hidden = !message;
}
function parse(buffer) {
  const a = new Float64Array(buffer),
    n = a[1],
    np = a[2],
    b = a[19];
  const packets = [];
  let offset = 20 + b * 12;
  for (let i = 0; i < np; i++) {
    const p = a.slice(offset + i * 11, offset + (i + 1) * 11);
    packets.push({
      id: i + 1,
      body: p[0],
      plan: p[1],
      speed: p[2],
      radius: p[3],
      specific_energy: p[4],
      eccentricity: p[5],
      periapsis: p[6],
      apoapsis: p[7] < 0 ? Infinity : p[7],
      target: p[8],
      radial: p[9],
      birth: p[10],
    });
  }
  return {
    time: a[0],
    n,
    np,
    enabled: !!a[3],
    halted: a[4],
    inner: a[5],
    outer: a[6],
    stored: a[7],
    heat: a[8],
    work: a[9],
    impulse: a[10],
    residual: a[11],
    capacity: a[12],
    force: a[13],
    retries: a[14],
    momentum: a[15],
    angular: a[16],
    boundary: a[17],
    mass: a[18],
    bodyCount: b,
    bodies: a.subarray(20, 20 + b * 12),
    packets,
  };
}
function send(kind, data = {}) {
  if (!worker) return Promise.reject(Error("Physics is still starting"));
  const id = ++requestId;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject, kind });
    worker.postMessage({ kind, id, ...data });
  });
}
function buttons() {
  $("play").disabled = !ready || !!world?.halted;
  $("launch").disabled = !ready || (world?.np || 0) >= 32 || !!world?.halted;
  $("reset").disabled = !ready;
  $("exportScene").disabled = !ready;
  $("play").textContent = playing ? "Ⅱ Pause" : "▶ Play";
  $("runState").textContent = ready
    ? world?.halted
      ? "Paused · model limit"
      : playing
        ? "Running"
        : "Paused"
    : "Starting";
}
function status() {
  if (!world) return;
  const w = world;
  let packet = w.packets.find((p) => p.body === selected) || w.packets.at(-1);
  $("population").textContent =
    `${w.n} elements · ${w.np} packet${w.np === 1 ? "" : "s"}`;
  $("packetCount").textContent = `${w.np} / 32`;
  if (w.halted) {
    $("decision").textContent =
      w.halted === 1 ? "Stellar approach limit" : "Numerical accuracy limit";
    $("detail").textContent =
      w.halted === 1
        ? "Paused before an object enters the unresolved stellar region. Reset and use a larger impact offset."
        : "A smaller step could not meet the energy-error bound. The last valid scene is retained; reset to explore another arrival.";
  } else if (!packet) {
    $("decision").textContent = "Cloud coasting";
    $("detail").textContent =
      "Launch an arrival at any time. The cloud keeps moving; packets share the same physical world.";
  } else if (!w.enabled) {
    $("decision").textContent = "Passive comparison";
    $("detail").textContent =
      "Only mutual gravity acts. Coupling uses no electrical energy.";
  } else if (packet.plan === 3) {
    $("decision").textContent = "Arrival declined";
    $("detail").textContent =
      "The budget screen estimates this arrival is beyond the available encounter impulse. Coupling conserves its resources.";
  } else {
    $("decision").textContent =
      packet.specific_energy < 0
        ? "Packet bound · continue observing"
        : packet.plan === 2
          ? "Limited assistance"
          : "Coordinated encounter";
    $("detail").textContent =
      packet.specific_energy < 0
        ? "Binding is one milestone. Inspect its closest and farthest approach to see whether it has reached a suitable parking orbit."
        : `Light-delayed local control aims toward a ${fmt(packet.target, 1)} AU parking region. Actual exchanges and resource limits determine the result.`;
  }
  $("stored").textContent = fmt((100 * w.stored) / (w.n * w.capacity), 1) + "%";
  $("heat").textContent = sci(w.heat) + " J";
  $("work").textContent = sci(w.work) + " J";
  $("balance").textContent = w.residual.toExponential(2) + " / reference";
  $("engineStatus").textContent = "REBOUND · local worker · v2.0";
  $("actualRate").textContent = playing ? rateText(actual) : "Paused";
  buttons();
  packetRegistry();
  inspect();
}
function acceptState(m) {
  const next = parse(m.buffer),
    old = world;
  previous =
    old && old.bodyCount === next.bodyCount && next.time > old.time
      ? old
      : null;
  world = next;
  blendMs = clamp(performance.now() - receivedAt, 30, 500);
  receivedAt = performance.now();
  if (m.kind === "reset" || m.kind === "load" || !old) {
    packetTrails.clear();
    cloudHistory = [];
    lastPacketCount = -1;
    selected = -1;
    inspecting = false;
    $("inspector").hidden = true;
  }
  for (const p of next.packets) {
    let t = packetTrails.get(p.id) || [];
    const b = p.body * 12;
    if (!t.length || t.at(-1)[3] !== next.time) {
      t.push([
        next.bodies[b],
        next.bodies[b + 1],
        next.bodies[b + 2],
        next.time,
      ]);
      if (t.length > 600) t.shift();
    }
    packetTrails.set(p.id, t);
  }
  if ($("cloudTrails").checked) {
    cloudHistory.push(next.bodies.slice(0, (next.n + 1) * 12));
    if (cloudHistory.length > 80) cloudHistory.shift();
  } else cloudHistory = [];
  if (m.kind === "init" || m.kind === "reset" || m.kind === "load") {
    $("count").value = next.n;
    $("inner").value = next.inner;
    $("outer").value = next.outer;
    $("offset").min = -next.outer;
    $("offset").max = next.outer;
    $("offset").value = clamp(+$("offset").value, -next.outer, next.outer);
    $("coord").checked = next.enabled;
    labels();
    home();
  }
  if (next.halted) playing = false;
  if (m.kind === "advance") {
    advancing = false;
    const now = performance.now();
    rates.push([now, next.time]);
    while (rates.length > 2 && now - rates[0][0] > 2000) rates.shift();
    if (rates.length > 1)
      actual =
        (next.time - rates[0][1]) / Math.max(0.001, (now - rates[0][0]) / 1000);
  }
  if (m.kind === "launch") {
    selected = next.packets.at(-1).body;
    inspecting = false;
    notice("");
  }
  ready = true;
  status();
}
function clamp(x, a, b) {
  return Math.max(a, Math.min(b, x));
}
async function openDatabase() {
  return new Promise((resolve, reject) => {
    const r = indexedDB.open("dyson-local-laboratory", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("scenes");
    r.onerror = () => reject(r.error);
    r.onsuccess = () => resolve(r.result);
  });
}
async function dbGet(key) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction("scenes", "readonly"),
      r = tx.objectStore("scenes").get(key);
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}
async function dbPut(key, value) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction("scenes", "readwrite");
    tx.objectStore("scenes").put(value, key);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}
async function digest(buffer) {
  const a = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(a), (v) =>
    v.toString(16).padStart(2, "0"),
  ).join("");
}
async function recordFor(m) {
  return {
    format: "dyson-local-scene-v2",
    snapshot: m.buffer,
    sha256: await digest(m.buffer),
    savedAt: Date.now(),
    engine: m.manifest.sha256,
  };
}
async function archive(record) {
  if (!record) return;
  previousRecord = record;
  $("downloadPrevious").hidden = false;
  if (db) await dbPut("retained-" + Date.now(), record);
}
async function save() {
  if (!ready || !storageOK || !db) return;
  if (saving) {
    saveAgain = true;
    return;
  }
  saving = true;
  try {
    do {
      saveAgain = false;
      const m = await send("save");
      const record = await recordFor(m);
      await dbPut("current", record);
      lastSaved = performance.now();
      $("saveStatus").textContent =
        "Saved in this browser · " +
        new Date(record.savedAt).toLocaleTimeString();
    } while (saveAgain);
  } catch {
    storageOK = false;
    $("saveStatus").textContent =
      "Browser storage is unavailable. This scene still works; Save scene file keeps a copy.";
  } finally {
    saving = false;
  }
}

async function boot() {
  notice("");
  ready = false;
  playing = false;
  buttons();
  if (worker) worker.terminate();
  pending.clear();
  worker = new Worker("/lab-assets/cloud-worker.js?v=2");
  worker.onmessage = async ({ data: m }) => {
    const task = pending.get(m.id);
    pending.delete(m.id);
    if (m.type === "error") {
      if (task) task.reject(Error(m.message));
      if (m.kind === "init") {
        notice(
          m.message +
            " Reload this page to retry; existing saved scenes are retained.",
        );
        $("engineStatus").textContent = "Physics engine unavailable";
      }
      return;
    }
    if (m.type === "state") {
      acceptState(m);
      if (m.kind === "init") {
        if (initialCandidate && !m.restored) {
          try {
            await archive(initialCandidate);
          } catch {
            storageOK = false;
          }
          notice(
            "The previous local snapshot could not be restored. It is retained; a new cloud is ready.",
          );
        }
        if (!storageOK)
          $("saveStatus").textContent =
            "Temporary scene: browser storage unavailable. Use Save scene file to keep it.";
        else save();
      }
    }
    if (task) task.resolve(m);
  };
  worker.onerror = () => {
    ready = false;
    playing = false;
    advancing = false;
    notice(
      "The local physics engine stopped unexpectedly. Reload to restore the latest saved scene; earlier data has been retained.",
    );
    buttons();
  };
  let snapshot = null;
  initialCandidate = null;
  try {
    db = await openDatabase();
    const saved = await dbGet("current");
    if (saved) {
      initialCandidate = saved;
      if (
        saved.format === "dyson-local-scene-v2" &&
        saved.snapshot instanceof ArrayBuffer &&
        saved.snapshot.byteLength <= 640000 &&
        saved.sha256 === (await digest(saved.snapshot))
      )
        snapshot = saved.snapshot.slice(0);
    }
  } catch {
    storageOK = false;
  }
  try {
    await send("init", { snapshot });
  } catch (e) {
    notice(e.message);
  }
}
$("play").onclick = () => {
  if (!ready) return;
  playing = !playing;
  lastTick = performance.now();
  credit = 0;
  rates = [];
  actual = 0;
  buttons();
  if (!playing) save();
};
$("launch").onclick = async () => {
  if (!ready) return;
  try {
    await send("launch", values());
    save();
    if (innerWidth <= 760) $("view").scrollIntoView({ block: "start" });
  } catch (e) {
    notice(e.message);
  }
};
$("reset").onclick = async () => {
  if (!ready) return;
  const n = +$("count").value,
    inner = +$("inner").value,
    outer = +$("outer").value;
  if (
    n < 240 ||
    n > 1800 ||
    !Number.isInteger(n) ||
    inner < 0.3 ||
    outer <= inner ||
    outer > 60
  ) {
    notice(
      "Use 240–1800 elements and an outer radius larger than the inner radius (up to 60 AU).",
    );
    return;
  }
  playing = false;
  credit = 0;
  buttons();
  try {
    await send("reset", {
      count: n,
      inner,
      outer,
      enabled: $("coord").checked,
    });
    notice("");
    save();
  } catch (e) {
    notice(e.message);
  }
};
$("coord").onchange = () => {
  if (ready)
    send("coord", { enabled: $("coord").checked })
      .then(() => save())
      .catch((e) => notice(e.message));
};
$("rate").onchange = () => {
  credit = 0;
  rates = [];
  actual = 0;
};
$("home").onclick = home;
$("closeInspect").onclick = () => {
  selected = -1;
  inspecting = false;
  $("inspector").hidden = true;
};
function download(value, name) {
  const blob = new Blob([JSON.stringify(value)], { type: "application/json" }),
    url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
function encodeBuffer(buffer) {
  const a = new Uint8Array(buffer);
  let s = "";
  for (let i = 0; i < a.length; i += 8192)
    s += String.fromCharCode(...a.subarray(i, i + 8192));
  return btoa(s);
}
$("exportScene").onclick = async () => {
  try {
    const m = await send("save"),
      r = await recordFor(m);
    download(
      { ...r, snapshot: encodeBuffer(r.snapshot) },
      "dyson-cloud-scene.json",
    );
  } catch (e) {
    notice(e.message);
  }
};
$("downloadPrevious").onclick = () => {
  if (previousRecord)
    download(
      {
        ...previousRecord,
        snapshot:
          previousRecord.snapshot instanceof ArrayBuffer
            ? encodeBuffer(previousRecord.snapshot)
            : previousRecord.snapshot,
      },
      "retained-dyson-scene.json",
    );
};
$("importScene").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const wasPlaying = playing;
  try {
    if (file.size > 1000000) throw Error("Scene file is too large");
    const r = JSON.parse(await file.text());
    if (r.format !== "dyson-local-scene-v2" || typeof r.snapshot !== "string")
      throw Error("This is not a local cloud scene");
    const raw = atob(r.snapshot),
      a = Uint8Array.from(raw, (c) => c.charCodeAt(0));
    if (a.byteLength > 640000 || r.sha256 !== (await digest(a.buffer)))
      throw Error("Scene checksum does not match");
    playing = false;
    credit = 0;
    buttons();
    const old = await recordFor(await send("save"));
    await send("load", { snapshot: a.buffer });
    try {
      await archive(old);
    } catch {
      storageOK = false;
    }
    save();
    notice("Scene loaded and paused. The previous scene is retained.");
  } catch (e) {
    playing = wasPlaying;
    lastTick = performance.now();
    buttons();
    notice(e.message + " The current scene is retained.");
  } finally {
    $("importScene").value = "";
  }
};

function packetStatus(p) {
  return p.specific_energy < 0
    ? "Bound orbit"
    : p.radial > 0
      ? "Outbound · unbound"
      : "Inbound · unbound";
}
function packetRegistry() {
  if (!world) return;
  if (lastPacketCount !== world.np) {
    $("packets").replaceChildren();
    packetButtons = [];
    for (const p of world.packets) {
      const button = document.createElement("button");
      button.className = "packet";
      button.dataset.packet = p.id;
      const left = document.createElement("span"),
        right = document.createElement("small");
      button.append(left, right);
      button.onclick = () => {
        selected = world.n + Number(button.dataset.packet);
        inspecting = true;
        inspect();
      };
      $("packets").append(button);
      packetButtons.push(button);
    }
    if (!world.np) {
      const p = document.createElement("p");
      p.className = "hint";
      p.textContent =
        "No packets launched. Use ＋ Launch packet below the view.";
      $("packets").append(p);
    }
    lastPacketCount = world.np;
  }
  for (let i = 0; i < packetButtons.length; i++) {
    const p = world.packets[i],
      b = packetButtons[i];
    b.children[0].textContent = "Packet " + p.id + " · " + packetStatus(p);
    b.children[1].textContent = fmt(p.radius, 1) + " AU";
    b.classList.toggle("selected", selected === p.body);
  }
}
function inspect() {
  if (!inspecting || selected < 0 || !world) {
    $("inspector").hidden = true;
    return;
  }
  if (selected >= world.bodyCount) return;
  const i = selected * 12,
    b = world.bodies,
    p = world.packets.find((p) => p.body === selected);
  $("inspector").hidden = false;
  $("inspectTitle").textContent =
    selected === 0 ? "Sun" : p ? "Packet " + p.id : "Element " + selected;
  const pairs = [
    ["Mass", b[i + 6].toExponential(3) + " kg"],
    [
      "Speed",
      fmt(Math.hypot(b[i + 3], b[i + 4], b[i + 5]) / 1000, 3) + " km/s",
    ],
    [
      "Radius",
      fmt(Math.hypot(b[i] - b[0], b[i + 1] - b[1], b[i + 2] - b[2]), 3) + " AU",
    ],
  ];
  let explain = "";
  if (p) {
    pairs.push(
      ["Orbit", packetStatus(p)],
      ["Closest approach", fmt(p.periapsis, 3) + " AU"],
      [
        "Farthest approach",
        Number.isFinite(p.apoapsis) ? fmt(p.apoapsis, 3) + " AU" : "unbounded",
      ],
      ["Eccentricity", fmt(p.eccentricity, 4)],
      ["Specific orbital energy", sci(p.specific_energy) + " J/kg"],
      ["Parking target", fmt(p.target, 2) + " AU"],
      [
        "Global decision",
        world.enabled
          ? ["", "Attempt capture", "Limited assistance", "Decline coupling"][
              p.plan
            ]
          : "Passive",
      ],
    );
    explain =
      "A negative orbital energy means bound now. A wide or elongated orbit is not yet a secured parking orbit, and later interactions can change it.";
  } else if (selected > 0) {
    pairs.push(
      ["Electrical store", fmt(100 * b[i + 7], 2) + "%"],
      ["Heat / capacity", fmt(100 * b[i + 8], 3) + "%"],
      ["Recent actuation", fmt(100 * b[i + 9], 1) + "%"],
    );
    explain =
      "This resolved element senses delayed arrivals and applies local commands subject to its finite force, power, energy, heat and orbit limits.";
  } else
    explain =
      "The Sun moves under the same mutual gravity equations. The view follows it; its physical position is not clamped.";
  $("inspectBody").replaceChildren();
  for (const [label, value] of pairs) {
    const row = document.createElement("div");
    row.className = "pair";
    const a = document.createElement("span"),
      v = document.createElement("strong");
    a.textContent = label;
    v.textContent = value;
    row.append(a, v);
    $("inspectBody").append(row);
  }
  const note = document.createElement("p");
  note.className = "explain";
  note.textContent = explain;
  $("inspectBody").append(note);
  packetRegistryHighlight();
}
function packetRegistryHighlight() {
  for (let i = 0; i < packetButtons.length; i++)
    packetButtons[i].classList.toggle(
      "selected",
      selected === world.packets[i].body,
    );
}
function home() {
  yaw = -0.5;
  tilt = 0.55;
  zoom = 1;
}
function center() {
  return world
    ? [world.bodies[0], world.bodies[1], world.bodies[2]]
    : [0, 0, 0];
}
function currentRadius() {
  if (!world) return 30;
  let r = world.outer;
  for (const p of world.packets)
    r = Math.max(r, Math.min(p.radius, world.outer * 3));
  return r;
}
function project(x, y, z = 0) {
  const c = center();
  x -= c[0];
  y -= c[1];
  z -= c[2];
  const a = x * Math.cos(yaw) - y * Math.sin(yaw),
    b = x * Math.sin(yaw) + y * Math.cos(yaw),
    h = b * Math.cos(tilt) - z * Math.sin(tilt),
    depth = b * Math.sin(tilt) + z * Math.cos(tilt);
  return [W / 2 + a * scale, H * 0.5 + h * scale, depth];
}
function path(coords, color, width = 1, dash = []) {
  ctx.beginPath();
  coords.forEach((p, i) => {
    const q = project(...p);
    i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.setLineDash(dash);
  ctx.stroke();
  ctx.setLineDash([]);
}
function circle(radius, plane, color, dash = []) {
  const c = center();
  path(
    Array.from({ length: 121 }, (_, i) => {
      const a = (i * Math.PI) / 60,
        p = [0, 0, 0];
      p[plane[0]] = radius * Math.cos(a);
      p[plane[1]] = radius * Math.sin(a);
      return p.map((v, k) => v + c[k]);
    }),
    color,
    1,
    dash,
  );
}
function aimGeometry() {
  const v = values(),
    a = (v.az * Math.PI) / 180,
    e = (v.el * Math.PI) / 180,
    q = (v.roll * Math.PI) / 180,
    r = world?.outer || 30,
    c = center();
  const d = [Math.cos(e) * Math.cos(a), Math.cos(e) * Math.sin(a), Math.sin(e)],
    side = [-Math.sin(a), Math.cos(a), 0],
    up = [-Math.sin(e) * Math.cos(a), -Math.sin(e) * Math.sin(a), Math.cos(e)];
  const offset = side.map(
    (x, i) => v.offset * (Math.cos(q) * x + Math.sin(q) * up[i]),
  );
  return {
    position: d.map(
      (x, i) => c[i] - (1.35 * r + 0.02 * (world?.np || 0)) * x + offset[i],
    ),
    velocity: d.map((x) => v.speed * 1000 * x),
    line: [-1.35 * r, 1.35 * r].map((t) =>
      d.map((x, i) => c[i] + t * x + offset[i]),
    ),
  };
}
function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min(0.25, (now - lastTick) / 1000);
  lastTick = now;
  if (ready && playing && !world.halted) {
    credit = Math.min(credit + dt * +$("rate").value, +$("rate").value * 0.5);
    if (!advancing && credit > 1e-8) {
      const days = credit;
      advancing = true;
      credit = 0;
      send("advance", { days })
        .then((m) => {
          credit = Math.min(
            credit + Math.max(0, days - (m.advanced || 0)),
            +$("rate").value * 0.5,
          );
        })
        .catch((e) => {
          playing = false;
          advancing = false;
          notice(e.message);
          buttons();
        });
    }
  }
  if (ready && storageOK && now - lastSaved > 3000 && !saving) save();
  draw(now);
  if (now - lastPaint > 250) {
    lastPaint = now;
    status();
  }
}
function draw(now) {
  const box = canvas.getBoundingClientRect(),
    dpr = Math.min(devicePixelRatio || 1, 2);
  if (W !== box.width || H !== box.height) {
    W = box.width;
    H = box.height;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#9bb6d344";
  for (const s of stars) {
    ctx.beginPath();
    ctx.arc(s[0] * W, s[1] * H, 0.65, 0, Math.PI * 2);
    ctx.fill();
  }
  if (!world) return;
  const w = world,
    c = center(),
    radius = currentRadius();
  scale = ((Math.min(W, H) * 0.38) / radius) * zoom;
  const mix =
    playing && previous ? clamp((now - receivedAt) / blendMs, 0, 1) : 1;
  displayTime =
    previous && playing
      ? previous.time + (w.time - previous.time) * mix
      : w.time;
  $("clock").textContent =
    displayTime < YEAR
      ? "Day " + fmt(displayTime, 1)
      : fmt(displayTime / YEAR, 2) + " simulated years";
  if ($("plane").checked) {
    const r = w.outer;
    path(
      [
        [-r, -r, 0],
        [r, -r, 0],
        [r, r, 0],
        [-r, r, 0],
        [-r, -r, 0],
      ].map((p) => p.map((x, i) => x + c[i])),
      "#6d9bc033",
    );
    for (let j = -2; j <= 2; j++) {
      const v = (j * r) / 3;
      path(
        [
          [-r, v, 0],
          [r, v, 0],
        ].map((p) => p.map((x, i) => x + c[i])),
        "#7aa8d01c",
      );
      path(
        [
          [v, -r, 0],
          [v, r, 0],
        ].map((p) => p.map((x, i) => x + c[i])),
        "#7aa8d01c",
      );
    }
  }
  if ($("bounds").checked) {
    for (const r of [w.inner, w.outer])
      for (const plane of [
        [0, 1],
        [0, 2],
        [1, 2],
      ])
        circle(
          r,
          plane,
          r === w.outer ? "#8eaac638" : "#d6c18b60",
          r === w.inner ? [3, 5] : [],
        );
    for (const [r, label] of [
      [w.inner, "Inner " + fmt(w.inner, 1) + " AU"],
      [w.outer, "Outer " + fmt(w.outer, 1) + " AU"],
    ]) {
      const q = project(c[0] + r, c[1], c[2]);
      ctx.fillStyle = "#91a6bc";
      ctx.font = "10px system-ui";
      ctx.fillText(label, q[0] + 5, q[1] - 5);
    }
  }
  if ($("earth").checked) {
    circle(1, [0, 1], "#7db6e978");
    const a = (displayTime / YEAR) * 2 * Math.PI,
      q = project(c[0] + Math.cos(a), c[1] + Math.sin(a), c[2]);
    ctx.fillStyle = "#80bff3";
    ctx.beginPath();
    ctx.arc(q[0], q[1], 3, 0, 7);
    ctx.fill();
    ctx.font = "10px system-ui";
    ctx.fillText("Earth · 1 AU reference", q[0] + 7, q[1] + 13);
  }
  const aim = aimGeometry();
  path(aim.line, "#8ef5cf58", 1, [5, 7]);
  const entry = project(...aim.position);
  ctx.drawImage(sprite("#ffd493"), entry[0] - 7, entry[1] - 7, 14, 14);
  const rendered = w.bodies.slice();
  if (previous && mix < 1)
    for (let i = 0; i < w.bodyCount; i++)
      for (let k = 0; k < 3; k++) {
        const p = i * 12 + k;
        rendered[p] =
          previous.bodies[p] + (w.bodies[p] - previous.bodies[p]) * mix;
      }
  if ($("cloudTrails").checked && cloudHistory.length > 1) {
    for (let i = 1; i <= w.n; i++) {
      const p = i * 12;
      path(
        cloudHistory
          .filter((_, k) => k % 3 === 0)
          .map((a) => [a[p], a[p + 1], a[p + 2]]),
        "#8fa8c21b",
        0.6,
      );
    }
  }
  if ($("trails").checked)
    for (const p of w.packets) {
      const t = packetTrails.get(p.id) || [],
        b = p.body * 12;
      if (t.length > 1)
        path(
          [...t.slice(0, -1), [rendered[b], rendered[b + 1], rendered[b + 2]]],
          colors[(p.id - 1) % colors.length] +
            (selected === p.body ? "dd" : "99"),
          selected === p.body ? 1.8 : 1.2,
        );
    }
  for (let i = 1; i <= w.n; i++) {
    const b = i * 12,
      link = w.bodies[b + 10],
      neighbor = w.bodies[b + 11];
    if (link > w.n && link < w.bodyCount) {
      const p = link * 12;
      path(
        [
          [rendered[b], rendered[b + 1], rendered[b + 2]],
          [rendered[p], rendered[p + 1], rendered[p + 2]],
        ],
        "#8ef5cf75",
        0.8,
      );
    }
    if (neighbor > 0 && neighbor <= w.n) {
      const p = neighbor * 12;
      path(
        [
          [rendered[b], rendered[b + 1], rendered[b + 2]],
          [rendered[p], rendered[p + 1], rendered[p + 2]],
        ],
        "#8ba8c628",
        0.6,
      );
    }
  }
  points = [];
  for (let i = 0; i < w.bodyCount; i++) {
    const b = i * 12,
      q = project(rendered[b], rendered[b + 1], rendered[b + 2]);
    points.push({ i, x: q[0], y: q[1], z: q[2] });
  }
  const ordered = points.slice().sort((a, b) => a.z - b.z);
  for (const q of ordered) {
    const i = q.i,
      p = i * 12,
      isSun = i === 0,
      isPacket = i > w.n,
      color = isSun
        ? "#ffdc98"
        : isPacket
          ? colors[(i - w.n - 1) % colors.length]
          : w.bodies[p + 9] > 0.01
            ? "#9af8d5"
            : "#90b8d5",
      size = isSun ? 34 : isPacket ? 15 : selected === i ? 14 : 9;
    ctx.drawImage(sprite(color), q.x - size / 2, q.y - size / 2, size, size);
    if (selected === i) {
      ctx.strokeStyle = "#ffffffaa";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(q.x, q.y, 8, 0, 7);
      ctx.stroke();
    }
    if ($("labels").checked && (isSun || isPacket || i % 20 === 0)) {
      ctx.fillStyle = "#b1c5d9";
      ctx.font = "9px system-ui";
      ctx.fillText(
        isSun ? "Sun" : isPacket ? "P" + (i - w.n) : "" + i,
        q.x + 6,
        q.y - 4,
      );
    }
  }
}
let drag = null,
  moved = 0;
canvas.onpointerdown = (e) => {
  drag = [e.clientX, e.clientY];
  moved = 0;
  canvas.setPointerCapture(e.pointerId);
};
canvas.onpointermove = (e) => {
  if (!drag) return;
  const dx = e.clientX - drag[0],
    dy = e.clientY - drag[1];
  moved += Math.abs(dx) + Math.abs(dy);
  yaw += dx * 0.006;
  tilt = clamp(tilt + dy * 0.006, -Math.PI / 2, Math.PI / 2);
  drag = [e.clientX, e.clientY];
};
canvas.onpointerup = (e) => {
  if (moved < 5) {
    const box = canvas.getBoundingClientRect();
    let best = 14;
    selected = -1;
    for (const p of points) {
      const d = Math.hypot(
        p.x - e.clientX + box.left,
        p.y - e.clientY + box.top,
      );
      if (d < best) {
        best = d;
        selected = p.i;
      }
    }
    inspecting = selected >= 0;
    inspect();
  }
  drag = null;
};
canvas.addEventListener(
  "wheel",
  (e) => {
    e.preventDefault();
    zoom = clamp(zoom * Math.exp(-e.deltaY * 0.001), 0.025, 100);
  },
  { passive: false },
);
canvas.onkeydown = (e) => {
  if (e.code === "Space") {
    e.preventDefault();
    $("play").click();
  }
};
function publicWorld() {
  if (!world) return null;
  return {
    ...world,
    bodies: Array.from({ length: world.bodyCount }, (_, i) => {
      const k = i * 12,
        a = world.bodies;
      return {
        id: i,
        x: a[k],
        y: a[k + 1],
        z: a[k + 2],
        vx: a[k + 3],
        vy: a[k + 4],
        vz: a[k + 5],
        mass: a[k + 6],
        energy: a[k + 7],
        heat: a[k + 8],
        active: a[k + 9],
      };
    }),
    packet: world.packets.at(-1) || null,
  };
}
window.cloudView = {
  get world() {
    return publicWorld();
  },
  get playing() {
    return playing;
  },
  get displayTime() {
    return displayTime;
  },
  get trails() {
    return packetTrails;
  },
  aimGeometry,
  project,
  get manifest() {
    return world ? true : false;
  },
  save,
};
labels();
buttons();
requestAnimationFrame(frame);
boot();
