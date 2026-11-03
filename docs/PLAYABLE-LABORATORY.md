# Playable gravity laboratory

## Explore the orbital sandbox

The Skunkworks interface is an asset-free, responsive 3D exhibit. **Play** (or
Space with the universe focused) animates acknowledged IAS15 samples. Drag to
orbit, shift-drag to pan, scroll/pinch to zoom, and click a physical body for its
gold trajectory. **Focus** expands the universe; Escape brings the controls back.
The X/Y/Z compass follows the camera. Background stars, emission halos and body
sizes are decorative, not additional simulated bodies or physical luminosities.

**Design an arrival** has paired sliders and exact numerical fields for speed,
signed offset, offset angle, mass, azimuth and elevation. Sliders redraw the mint
draft immediately, without a request or a numerical integration. The dashed
line is initial aim geometry; the solid arrow represents 30 days of displacement
at the specified initial velocity **without acceleration**. Neither is a gravity
forecast. **Frame aim** fits the insertion region without changing the world.

Pause and use **Trace gravity** for 97 actual IAS15 N-body samples on an isolated
copy with the proposed body inserted. This includes the same massive-body back
reaction as a real insertion. It never advances or inserts into the saved world.
Amber is this forecast; mint is draft geometry. Changing parameters, resetting,
launching or advancing invalidates the forecast. Trace is explicit rather than
an expensive automatic request on every slider movement; the existing weighted
session quota applies. Rejected, stale or failed previews leave the world intact.
Forecasts remain bounded to at most two years (unbound arrivals: 180 days), with
no future insertions or control. Sparse joined samples are not precision encounter
or collision guarantees.

**Launch arrival** commits the exact configured initial state. The dock stays
available while exploring, including on mobile. Jump links locate launch, world,
inspection and measurement controls. **Quick start** explains the interaction.
World sliders apply with **New cloud**; existing worlds are never silently reset.
The 1-hour to 20-year target rate range and exact **Advance selected interval**
remain available. Throughput is backend-limited, and long advances commit bounded
steps; the render and committed clocks remain separately visible.

The existing presets, deterministic replay, measured plots, pinned comparison,
exports, reference frames, visibility options and save/recovery operations remain.
Save/checkpoint/private backup controls are grouped in **Save & recover your
universe**. Open that disclosure before downloading or importing. Private recovery
semantics and ownership are unchanged. The cloud still has the existing 200-body
limit; this does not claim the original prototype's 900-agent visual density.

This workbench extends the existing REBOUND explorer. It is a Newtonian point-mass
experiment environment, not a demonstrated interstellar capture device. Synthetic
Sun–Earth initial conditions are not measured ephemerides. The physical solver,
SQLite ownership, signed checkpoints and private recovery remain the same.

## Run the current development software

From a checkout of `foundation/rebound-ci` after this milestone is integrated:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 in a WebGL-capable browser. Windows users can use
`.venv\Scripts\python.exe` in place of `.venv/bin/python`. Session data stays in
`.session-data`; preserve it for ordinary local resumption. Existing private
recovery remains conditional on a stable configured recovery key; the UI states
when redeploy recovery is unavailable. Never share private backup credentials.
No production hosting changes are required by this launch method.

## Experiments to try

1. **Inclined flyby:** load the preset, Replay scenario + arrival, select/follow
   the tracked body, step 30 days several times and inspect its Sun-relative
   distance, speed, radial motion, osculating elements and measured vector momentum/kinetic-energy change at object scale. Pin the run, reduce
   speed, replay and compare distance curves at matched simulation times.
2. **Bound at entry:** load that preset and replay. Negative two-body energy is
   an initial condition, not evidence of capture. Watch how the orbit changes
   under the same full N-body gravity as the cloud and planets.
3. **Massive-body recoil:** load that preset and replay. Change arrival mass,
   inspect the moving Sun/Earth and the insertion ledger. This is a hypothetical
   mass assumption, not a spacecraft or collision model.
4. **Cloud design:** adjust population, mass, inner/outer radius and plane tilt;
   Reset cloud or Replay applies the deterministic setup. Compare sparse light
   clouds with more massive interacting clouds. Remember/Recall stores setup
   locally without changing the current world until applied.
5. **Record the experiment:** export JSON for solver/version, scenario,
   insertion events, final state, bounded measured samples and pinned comparison.
   This sanitized result has no recovery credential and cannot restore a private
   session. Use the existing private checkpoint/backup controls for restoration.

Rotate, zoom, shift-drag pan, top/side view, origin selection and follow are visual
operations. Sphere markers are enlarged. Paths join acknowledged states only;
no second visual physics engine extrapolates them. Earth and the selected-body
paths and plots keep at most 500 samples (Earth legacy path is separately capped
at 1000); selected cloud-body history begins when that body is selected. Plots
and pinned references are tab-local and are not recovered with physical backups.

## Scientific interpretation and boundaries

- Gravity remains mutual Newtonian N-body IAS15 with a moving Sun. New default
  Sun/Earth/72 one-kilogram clouds use a deterministic spherical ensemble (scenario
  version4). Existing disk checkpoints preserve their original coordinates; use
  Load spherical cloud to explicitly start the new scenario.
  Parameterized geometry is deterministic and stored in physical checkpoints.
- Arrival position is 5.6 AU upstream in the chosen velocity direction plus the
  signed impact offset in its perpendicular plane. Azimuth/elevation orient the
  velocity; offset angle rotates the perpendicular vector. Arrival velocity is
  specified in the initial inertial frame, not relative to a moving Sun.
- Arrival addition is an external matter injection, not a funded propulsion
  maneuver. Its append-only journal records time, parameters, mass, vector
  momentum, angular momentum and added kinetic plus new pair-potential energy.
  Energy drift is rebaselined after each insertion and monitors only subsequent
  closed integration. Sun-scale residuals can hide small-body error. The ledger
  is state accounting, not independent experimental validation or proof of a
  feasible launch/capture mechanism. Old backups may predate this journal.
- Measured object momentum/kinetic-energy changes use the initial inertial frame
  and the first retained sample; they measure gravitational exchange, not an
  actuator or capture budget.
- Distance, speed and radial velocity use Sun-relative state. Specific orbital
  energy, eccentricity and periapsis use the instantaneous two-body Sun/object
  approximation; they are diagnostics of the N-body state, not predictions or a
  capture criterion. Sampled minima miss encounters between samples.
- Arrival speed is capped at 300 km/s in this sandbox. That conservative input
  bound is not a validated mission accuracy envelope. No relativity, strong-field
  validation, collision/contact, material capture, finite-size radii, thermal
  hardware, photon/tether coupling or funded controller is implemented. High
  masses/close encounters may cost time and produce physically inappropriate
  point-mass trajectories; no precision close-encounter claim is made.
- Runtime remains the existing REBOUND 4 range; the approved v5/REBOUNDx target
  is not silently migrated. IAS15 adaptive internal history is not in JSON
  recovery; restart remains tolerance-tested, not bitwise solver continuation.

The next substantial milestone should select and independently validate a
specific finite-resource actuator/coupling reference before enabling a capture
or momentum-exchange controller. This deliverable supplies gravity baselines,
replay and diagnostics for that investigation without inventing that mechanism.


## Prototype core parity repair

The actual archived v0.14 HTML was recovered and byte-verified with SHA-256
`ca2092e8b4a20b759284e5fd9c75adb157e636ad40688891bf055b5c8f1a2fd3`
(44,367 bytes). It was executed in Chromium: 900 visible agents had independent
radial/tangential directions, motion changed during Play, launch added an object,
and rates included 2 years/s. Its HTML title says0.12 while its visible header
says0.14; the archived artifact was not replaced with a reconstruction. The old
fixed-Sun integrator and coupling proxies were not copied into the REBOUND model.

New worlds now start with a spherical isotropic ensemble. Disk/tilted geometry
remains available, and saved worlds are never silently rewritten. A prominent
Load spherical cloud action upgrades an old disk world by explicit reset. The
existing202-body ceiling remains: this restores core interaction, not the old
900-body visual population or unvalidated capture/controller behavior.

Play renders between dense positions actually sampled by IAS15; it never
extrapolates uncomputed physical motion. The render and committed clocks are both
shown. Rates restore the original1hour through20years of target simulated time per real second;
actual throughput depends on the backend. Advance selected interval commits the
chosen total exactly, including2years (63,115,200 seconds), using sequential
steps of at most30days. Stop advance preserves progress after the current step;
uncertain requests are not repeated automatically. Pausing Play stops future
requests after any in-flight chunk. No integration/body/quota limit is increased.

Click a body or choose it in the object list to draw a gold full-N-body REBOUND
forecast on a copy. It is sampled97times over up to2years (one estimated orbit
when shorter;180days for unbound objects). It is a no-future-insertion/control
forecast, not a circular visual proxy or an exact future observation. Blue paths
remain measured history. Forecasts cost25existing quota units, bounding CPU work
without raising the request allowance. Camera rotation/zoom/pan remain unchanged.

Deployed acceptance runs only on explicit dispatch of the existing verification
workflow, against the fixed existing Skunkworks URL and exact dispatched commit.
It opens a fresh isolated browser session, observes actual projected movement,
clicks a body/trajectory, rotates/zooms, launches, and confirms a full2-year
advance. JSON observations and desktop/mobile screenshots are retained with CI.
This check cannot be replaced with a local suite or Render live status alone.
