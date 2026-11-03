/* Standalone GPL REBOUND executable lives behind this worker message boundary. */
"use strict";
let engine = null,
  manifest = null;
function state(kind, id, extra = {}) {
  const length = engine._cloud_state(),
    pointer = engine._cloud_output() / 8;
  const values = engine.HEAPF64.slice(pointer, pointer + length);
  postMessage({ type: "state", kind, id, buffer: values.buffer, ...extra }, [
    values.buffer,
  ]);
}
async function initialize(message) {
  const response = await fetch("/lab-assets/engine/manifest.json", {
    cache: "no-store",
  });
  if (!response.ok) throw Error("Physics assets could not be loaded");
  manifest = await response.json();
  importScripts("/lab-assets/engine/" + manifest.runtime);
  engine = await createCloudEngine({ print: () => {}, printErr: () => {} });
  let restored = false;
  if (message.snapshot) {
    try {
      const a = new Float64Array(message.snapshot);
      if (a.length >= 24 && a.length <= 80000) {
        engine.HEAPF64.set(a, engine._cloud_snapshot() / 8);
        restored = !!engine._cloud_restore(a.length);
      }
    } catch {}
  }
  if (!restored && !engine._cloud_reset(900, 1, 30, 122333))
    throw Error("Could not construct the initial cloud");
  state("init", message.id, { restored, manifest });
}
onmessage = async ({ data: m }) => {
  try {
    if (m.kind === "init") {
      await initialize(m);
      return;
    }
    if (!engine) throw Error("The physics engine is still starting");
    if (m.kind === "reset") {
      if (!engine._cloud_reset(+m.count, +m.inner, +m.outer, 122333))
        throw Error(
          "Use 240–1800 elements and an outer radius larger than the inner radius (up to 60 AU)",
        );
      engine._cloud_coordination(m.enabled ? 1 : 0);
      state("reset", m.id);
      return;
    }
    if (m.kind === "load") {
      const a = new Float64Array(m.snapshot);
      if (a.length < 24 || a.length > 80000)
        throw Error("Scene layout is invalid");
      engine.HEAPF64.set(a, engine._cloud_snapshot() / 8);
      if (!engine._cloud_restore(a.length))
        throw Error("Scene layout is invalid");
      state("load", m.id);
      return;
    }
    if (m.kind === "launch") {
      if (!engine._cloud_launch(+m.speed, +m.offset, +m.az, +m.el, +m.roll))
        throw Error(
          "Arrival outside model limits, or the 32-packet capacity has been reached",
        );
      state("launch", m.id);
      return;
    }
    if (m.kind === "coord") {
      engine._cloud_coordination(m.enabled ? 1 : 0);
      state("coord", m.id);
      return;
    }
    if (m.kind === "advance") {
      const advanced = engine._cloud_advance(Math.min(3652.5, +m.days), 25);
      state("advance", m.id, { advanced });
      return;
    }
    if (m.kind === "save") {
      const length = engine._cloud_save(),
        pointer = engine._cloud_snapshot() / 8;
      const snapshot = engine.HEAPF64.slice(pointer, pointer + length);
      postMessage(
        {
          type: "snapshot",
          id: m.id,
          buffer: snapshot.buffer,
          format: 24001,
          manifest,
        },
        [snapshot.buffer],
      );
      return;
    }
  } catch (problem) {
    postMessage({
      type: "error",
      id: m.id,
      kind: m.kind,
      message: problem.message || String(problem),
    });
  }
};
