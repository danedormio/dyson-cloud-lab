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
