# First playable 3D explorer increment

The existing REBOUND snapshot supplies all positions, velocities and masses. The
viewer uses WebGL triangle meshes with perspective, depth testing and lighting.
Positions are converted from SI float64 values to AU only for rendering. Sphere
radii and colors are viewing aids, not collision geometry, physical size, heat or
hardware status. The planar synthetic initial cloud is unchanged; camera rotation
reveals its plane. Launch with an offset angle to place an incoming body out of
that plane. Reference rings are guides, not force boundaries.

Drag (or one-finger drag) rotates, wheel/pinch zooms, Reset camera/Home restores
the initial view. Arrow keys rotate; +/- zoom. Click selects the nearest visible
body under the cursor; the object list also reaches hidden/offscreen bodies.
Inspection reports the current backend mass, position, velocity and frame.
Cloud visibility, labels, Earth trail and reference rings affect display only.
Earth trails sample accepted snapshots, are bounded to 1000 samples and are not
an interpolated orbit prediction. Camera, selection and trails are ephemeral and
are not part of scientific checkpoints.

Play requests one bounded backend step per second when ready. Rate means 1 hour,
1 day or 1 week **per accepted step**, not guaranteed wall-clock simulation speed.
Pause stops issuing steps; an already submitted step may finish. +1 day always
advances one day. Reset stops playback and uses the existing deterministic backend
reset with the chosen population. Mutation controls are disabled during an
in-flight action. Uncertain requests are never automatically repeated. Existing
private checkpoint, IndexedDB and signed recovery paths are retained.

This deliberately small, dependency-free WebGL viewer does not introduce Three.js
or the planned full catalog/floating-origin framework. It is bounded to the
existing solar-system scene and 202-body backend limit; distant/far-away bodies
can clip at the viewing range. WebGL unavailable/lost states are disclosed and
list-based inspection remains available. Context restoration rebuilds rendering
buffers; it does not recreate physics state.

No solver/dependency migration, new forces, capture, propulsion, thermal/resource
model, ephemeris, or physical-validation claim is included. Existing Newtonian
model limitations (including the pre-existing high-speed launch range) remain.
The historical v0.14 interface informed control vocabulary only; no prototype
physics or historical source is bundled.

Verification includes browser pixel readback, camera and picking interactions,
backend-state invariance under viewing, play/rate/pause/reset, responsive layout,
WebGL-unavailable inspection and all existing private recovery scenarios. Physics
checks compare all UI rate values with direct IAS15 integration, energy/momentum
thresholds and exact deterministic reset. CI success is software regression
evidence, not validation of new scientific capabilities.

## Staging build identity (Issue #10)

The header shows `Build: <full commit SHA>` from the server's latest successful
`/health` response, or `Build: unknown`. Render supplies `RENDER_GIT_COMMIT` by
default ([Render reference](https://render.com/docs/environment-variables)).
The server captures it at application creation and accepts only a full 40-digit
hexadecimal Git SHA, normalized to lowercase. Missing, empty, abbreviated or
malformed values become `unknown`; no checkout lookup, guessed revision or
arbitrary environment contents are exposed. Health responses use `no-store` and
reading the revision neither creates a session nor changes simulation state.

The indicator refreshes through existing readiness/reconnect checks. It reports
server metadata, not an independent attestation, a guarantee that an old browser
loaded identical frontend assets, or a promise that every replica has the same
revision during rollout. An unreachable server cannot supply a new revision.
Outside Render, operators may supply the same non-secret variable for a known
build; otherwise `unknown` is intentional. No hosting configuration is changed.

API tests cover full/uppercase/missing/empty/abbreviated/unsafe values and a stable
per-app revision. Real Chromium checks compare both known and unknown displays
against the running server response, retain the indicator after a physics step,
and check mobile width. The full existing regression suites remain required.
