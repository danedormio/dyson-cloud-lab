# Orbital cloud — playable 900-body baseline

Open `/simple` on the existing Skunkworks development service. It starts paused
with **900 resolved masses**, not decorative tracers. Press Play, choose a
playback target from one hour to twenty years per second, and launch arrivals
into the moving cloud. Launch preserves playback and all previous packets;
Reset creates a new paused cloud. There is capacity for 32 simultaneous packets.
Successive arrivals start 0.02 AU farther back so paused launches never create
coincident point masses. The dashed line is initial aim, not a gravity forecast.

Drag to rotate, scroll to zoom, click a body or packet list entry to inspect.
The ecliptic, inner/outer spheres and Earth marker are switchable visual guides.
Earth is a **1 AU reference**, not a massive planet in this scene. Packet trails
are sampled computed history. Cloud trails and labels are optional. Arrival
speed, signed offset, direction and optional tilt/offset rotation set true 3D
initial conditions. Cloud count/radii apply on Reset, without inflating mass.

The experimental question is observable: reset to the same cloud, launch the
same arrival with coordination on/off, and inspect its instantaneous energy,
closest/farthest approach, resource use and controller decision. The default
45 km/s, 5 AU arrival becomes bound under the ideal controller in the validated
1380-day fixture; the passive comparison stays unbound. A bound elongated orbit
is **not secured parking**. Faster arrivals can be declined. This milestone is
an extensible control experiment, not a transport-feasibility finding.

## Execution and preservation

`simple.html`, `static/cloud-lab.js` and `static/cloud-lab.css` own presentation.
`static/cloud-worker.js` owns the message protocol; a standalone C/WebAssembly
executable runs REBOUND and controllers. The view never calls a server simulation
API. An expired old session cannot block a new scene. Python backend/API worlds
remain available at `/`; the exact previous First Light workbench is retained
at `/simple-legacy`, with its old API and recovery tests. Historical design and
owner-rejected handoffs are preserved in `HISTORY-FIRST-LIGHT.md`; they are not
acceptance evidence for this baseline. Notion remains the canonical project record.

New scenes use a separate IndexedDB namespace, `dyson-local-laboratory`.
Snapshots include all resolved bodies, per-element reservoirs, controllers,
delayed observation history and insertion ledgers. Checksums and full structural
validation precede restore. An invalid record is retained, and a fresh usable
cloud appears automatically. Blocked storage gives a usable temporary scene;
Save scene file exports a copy. Old cookies, backups and server worlds are not
deleted, imported or overwritten. Restored scenes always start paused.

## Physical and numerical contract

- SI barycentric Newtonian direct mutual point-mass gravity, unmodified REBOUND
  4.6.0, moving Sun (1.98847e30 kg), G=6.67430e-11. AU=149597870700 m;
  day=86400 s; year=365.25 days. Display follows the Sun; physical position is
  never pinned. No absolute ephemeris epoch is claimed.
- Deterministic seed 122333, isotropic circular orbital planes, stratified radii
  1–30 AU by default. Count 240–1800; inner radius >=0.3 AU and outer <=60 AU.
  Fixed allocated cloud mass 9e20 kg is within a provisional ~3e21 kg asteroid
  inventory. Count changes share fixed total mass/actuator/storage capacity.
  No extraction, composition, construction or technology feasibility claim.
- Packet mass 1e12 kg; speed 5–3000 km/s (~0.01c maximum). Each insertion records
  energy, linear and angular momentum crossing the simulated boundary; it is
  not a funded launch maneuver. All packets gravitate with all other objects.
- WHFast with direct full gravity, synchronized before impulses/diagnostics;
  coast step <=32*(inner/AU)^1.5 days. Encounter control step
  clamp(0.05*(packet-radius/AU)^1.5,0.125,1) days. Symmetric gravity/impulse/gravity
  splitting; packet crossing-time cap 0.05*r/v prevents stepping over a stellar
  approach. No physics time multiplier. Energy guard rejects/retries at half
  steps, up to eight reductions; unresolved r<0.08 AU or excessive residual
  pauses explicitly. This does not guarantee arbitrary close-encounter accuracy.
- Energy residual is (mechanical+electrical+heat−initial−boundary) divided by
  **1e12*(45000 m/s)^2** (2.025e21 J), with acceptance <1e-4. It is not hidden
  under a Sun/cloud-scale relative error. Compensated sums monitor P and L.
  IAS15 epsilon1e-10 is the independent reference mode, not the interactive
  default. Rate selection changes requested duration, not forces/tolerances;
  the actual achieved rate is displayed when computation is slower.
- Central pair impulses have equal/opposite reaction and zero instantaneous
  pair torque. Exact kinetic work includes both masses. Each default element
  has 2e9 N force, 2e14 W work rate, 2e22 J electrical capacity (half full), 90%
  conversion efficiency and retained heat ceiling0.25*capacity. Limits scale
  as900/count. Absolute impulse allowance is shared across packets and neighbor
  interactions per element per tick; work allowance is shared per owning actuator.
  Positive work drains storage; negative work regenerates with loss heat.
  No free recharge/cooling, clamp, hidden drag or unlimited energy reservoir.
- Both cloud participants reject commands outside a 5% initial orbital-energy
  envelope or >2 m/s impulse delta-v; these are monitored local action vetoes,
  not guaranteed long-term stable orbits. Orbital KE/gravity supply the mechanical
  reservoir. An important orbit is not artificially held in place.
- Ideal coupling reach2 AU is a Newtonian central-actuator abstraction; no
  electromagnetic hardware or propagating field momentum is modeled. The
  global impulse/time heuristic chooses attempt/limited-assistance/decline and
  a parking radius. It is not an optimal resource-feasibility proof. Local
  decisions use light-delayed observations and constant-velocity prediction,
  proportional projected velocity correction and resource vetoes. Global
  observation/broadcast travel is delayed; remote observations obey range/c.
  Locally sensed nearest neighbors weakly damp radial relative velocity.
- No collisions, cooling, surface effects, engineering or relativistic motion.
  Decline disables coupling; it does not demonstrate a funded avoidance maneuver.
  Planetary ephemerides/dynamics and stable multi-orbit traffic planning remain
  later layers. Guide markers exert no force and must never be reported as
  physically simulated planets.

## Numerical evidence and limits

`tests/test_local_engine.py` compiles the same C/upstream source natively and
checks inventory/back reaction, long coasting, IAS15 comparison, direct central
exchange work/P/torque, insertion boundary ledgers, multiple packets, full save
roundtrip/invalid input, controller refinement and passive/declined comparisons.
It also executes the shipped WebAssembly in Node and compares body trajectories
against native output. The source archive and runtime hash are verified.

Measured native comparisons before publication:
- 24-body ten-year coast: maximum Cartesian difference WHFast vs IAS15
  2.82e-12 AU; 900-body eight-day coast:7.11e-15 AU.
- Default900-body encounter at1380days: WHFast vs IAS15 same control intervals
  differ ~2.4e-5 J/kg in packet energy (~1.3e-12 relative), with negative
  energy−1.898e7 J/kg, periapsis4.03 AU, apoapsis42.7 AU. This validates gravity
  agreement for this fixture, not arbitrary scenarios or the control assumptions.
- Half/quarter control intervals give energy−1.777e7/−1.776e7 J/kg and
  apoapsis45.83/45.87 AU. Default coarse apoapsis differs by ~7%; half vs quarter
  differs <0.1%. Control discretization dominates this example. Do not quote
  interactive coarse outcomes as precision research results. Binding agrees
  across these refinements; guaranteed durable capture is unestablished.
-900-body ten-year coasting residual2.9e-6 of the packet reference scale.
  Shared hardware throughput varies; native timings are not browser guarantees.

Browser tests use real Chromium and the distributed worker, including visible
reference pixel changes,900-body movement, all playback controls, multiple live
and paused launches, paused recovery, expired old cookies, blocked storage,
corrupt retained snapshots,3D aiming, camera and mobile controls. Legacy tests
continue to cover the preserved server workbench. Hosted acceptance must match
the actual deployed revision separately from local/PR CI.

## Rebuild and component license

The standalone physics executable and its glue/controller are GPL-3.0-or-later,
with upstream attribution and exact corresponding source. `engine/vendor`
contains the pinned upstream archive and notice; `/lab-assets/engine/` serves
both executable and complete source archive. This component notice does not
relicense existing project/UI/research. No commercial compatibility assumption.

`engine/build_native.sh` uses GCC. `engine/build_wasm.sh` uses official Emscripten
4.0.10; `engine/package_build.py` names the runtime by SHA256 and packages source.
Render serves checked-in assets and needs no new compiler, service or paid plan.
The source build CI checks generated bytes against the shipped runtime hash.
