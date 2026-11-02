# Playable gravity laboratory

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
   distance, speed, radial motion and osculating elements. Pin the run, reduce
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

- Gravity remains mutual Newtonian N-body IAS15 with a moving Sun. Default
  Sun/Earth/72 one-kilogram cloud conditions retain the existing fixture.
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
