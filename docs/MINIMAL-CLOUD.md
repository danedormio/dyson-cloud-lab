# First Light — minimum coordinated-cloud milestone

Open `/simple` on the existing development service. The old workbench and saved
worlds remain available at `/`; this milestone does not replace them or migrate
private data. The new scene uses the same ownership, request limits and signed
checkpoint system, with its own nested physical state.

Use the default 45 km/s, 0.65 AU arrival first. Launch and let time advance.
The dashed line is straight initial aim geometry, not a gravity forecast.
The amber trail is actual sampled packet history. Mint links show active
packet–station interaction. Reset, turn coordination off, and launch again.
Every launch starts from the same initial cloud phase for a fair comparison.
Next try 80 km/s (limited assistance) and 180 km/s (stand aside).

## Model contract

- Version `minimal-cloud-v1.1`; SI barycentric Newtonian mutual point-mass gravity,
  REBOUND 4 IAS15, epsilon 1e-10, initial dt 7200 seconds, minimum internal dt
  1 second. Control is symmetric gravity/impulse/gravity splitting at 7200-second
  ticks. Plan/sensing delays round up to a control tick. No relativistic regime.
- Forty-eight resolved stations in three planar rings, 0.8, 1.2 and 1.6 AU;
  a deterministic small phase perturbation avoids numerically degenerate exact
  symmetry. This is deliberately a flat, small cloud, with camera tilt rather
  than a claim of a spherical population. Each station is 1e18 kg. Total 4.8e19
  kg = 8.04e-6 Earth masses, allocated from the provisional asteroid-belt ceiling
  of approximately 0.0005 Earth masses in the canonical inventory ledger.
  Composition, extraction/construction work, hardware feasibility and industrial
  availability are not established by this allocation.
- One packet: 1e12 kg; arrival 5–180 km/s, signed offset and approach angle.
  Its insertion is an open-boundary event. Conservation baselines restart at
  insertion; there is no claim of funded launch propulsion.
- Ideal bidirectional central actuators within 0.65 AU, maximum 2e9 N and 2e14 W
  per link. Distance is an eligibility check, not a physical field law. No claim
  of an electromagnetic realization or physically validated AU-range coupling.
  Forces have equal-and-opposite reaction, zero instantaneous pair torque, and
  exact finite-impulse kinetic work. Momentum in real propagating force fields
  is NOT modeled; this is a Newtonian ideal actuator approximation, whereas
  controller communications/measurements are explicitly delayed.
- Each station has a 2e22 J electrical capacity, initially half full, 90%
  bidirectional conversion efficiency, and a heat ceiling of 25% of electrical
  capacity. Heat is retained, with no cooling or free recharge. Positive work
  costs store energy; negative work regenerates and adds loss heat. There is no
  independent elastic reservoir in v1: mechanical energy is resolved orbital KE
  and gravity. No arbitrary reset of positions, velocities or orbit energy.
- Per-link force/work caps, station speed/delta-v checks, and a 5% initial
  specific-orbital-energy envelope reject unaffordable commands. These are
  controller constraints, not guaranteed long-term orbital safety. Packet approaches
  inside 0.08 AU pause the simulation before the unresolved stellar region.
- Global budget screen uses estimated encounter time and impulse/energy demand.
  It selects attempt, assist, or stand aside. It is a heuristic, not an optimal
  feasibility proof. One target: near-circular prograde/retrograde motion toward
  the 1.2 AU region, with direction selected from packet angular momentum.
- Station decisions: delayed packet observation, constant-velocity prediction,
  projected proportional action toward target velocity, and local resource veto.
  Nearest ring neighbors use locally sensed radial relative-velocity damping.
  Global plan travel includes incoming observation and outgoing broadcast delay.
  Remote packet observations have range/c age; finite control ticks limit timing
  precision. Neighbor sensing is a local ideal observation at each control tick.
- Stand aside disables coupling; there is no finite-size collision or funded
  avoidance maneuver. Point masses pass through without collision. The interface
  says this explicitly. Do not interpret it as demonstrated avoidance safety.
- “Bound now” is instantaneous negative two-body osculating energy relative to
  the Sun. It is not proof of durable capture. All claimed outcomes are specific
  to the stated ideal capabilities and controller.

## Verification and limits

Tests compare gravity-only and controlled runs, half-step refinement, exact pair
work/momentum/torque, store refusal, delayed plan reception, session isolation,
checkpoint restart and repeated initial phase. Full-system floating sums have
an absolute roundoff floor: pair closure is checked against 8 ULP of the total
sum; long-run energy residual is also normalized to a fixed packet energy scale
(1e12 kg × (45 km/s)^2), rather than hidden under Sun-scale relative drift.

The browser test uses actual pointer controls, actual backend motion, launch,
selection, reset, passive/stand-aside paths and mobile layout. Earlier exact
symmetry stalled IAS15 in the no-packet case; the asymmetric deterministic
baseline and explicit numerical settings resolve that failure. No-packet and
restart regression tests retain coverage of it.

## Source preservation and delivery

Base commit: `579b5a27346aba60d61117a98e740b985dc5c0c4`.
Base tree: `73443ac243824df9989b3030e5ed1c9f09b141fe`.
The pre-existing `/workspace/dyson-cloud-lab` checkout is a clean old main
snapshot (`2ae4926...`) and was excluded from implementation. Shell Git transport
could not reach its configured proxy. The GitHub plugin verified and created
`feat/minimal-coordinated-cloud` from the exact development base. Text files were
retrieved by immutable commit into `/workspace/work/minimal-cloud`; binary
historical evidence was not downloaded. This is a partial working snapshot,
not a synchronized Git clone. Publication preserves the complete remote base
tree and changes only intended paths through the supported GitHub workflow.
No production, deployment configuration, permission, licensing, account, cost or
schedule changes are included. Existing dependencies and research remain intact.

## Free-host performance correction

The actual hosted v1 journey exposed roughly 11-second two-day updates after
launch on the existing free CPU allocation. Version1.1 uses an explicit two-hour
controller interval instead of30minutes, while IAS15 gravity remains adaptive.
This reduces controller/integrator-restart work by4x. Finite signal travel is
still enforced, with decisions quantized to the controller interval; this is a
coarse control model, not sub-hour response fidelity. The half-interval comparison
now checks two-hour against one-hour control. The stellar stop radius is0.08AU
to retain margin for the longer control interval. No forces or resource limits
are increased to improve apparent capture.
