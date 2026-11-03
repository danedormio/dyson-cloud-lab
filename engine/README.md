# Local REBOUND physics executable

This separate browser-worker executable uses unmodified REBOUND 4.6.0 for full
mutual Newtonian gravity, including stellar back reaction. Its controller applies
central reaction impulses with finite force, power, stored energy and heat. It
runs in a worker so simulation work does not block viewing or UI controls.

REBOUND and this executable's glue/controller source are GPL-3.0-or-later. The
upstream notice/license and exact corresponding source are included alongside
the build scripts; the browser download directory also contains a complete
corresponding-source archive. This third-party component notice does not relicense
the project's research records, historical prototype or other existing files.
REBOUND: Hanno Rein and contributors, https://github.com/hannorein/rebound/.
Source archive SHA256: 46e2edda7c6e88444e8c7dd095aa4040f558079a19f62d918d56c0d68b9500e3.

Build with Emscripten 4.0.10 using `engine/build_wasm.sh`; native validation uses
`engine/build_native.sh` and the same C/upstream source. No simulator math is
substituted in JavaScript. Renderer guides (ecliptic, boundary spheres and the
1 AU Earth reference) exert no forces and are labeled as reference guides.

The interactive solver is REBOUND WHFast with full direct mutual gravity.
Coasting steps are longer in a dilute, star-dominated cloud; packet coupling
uses smaller symmetric gravity/impulse/gravity steps. A packet-scale total-energy
residual guard retries smaller steps instead of accepting excessive drift.
IAS15 remains the independent reference/validation mode. Solver migration must
pass numerical comparisons, conservation, near-encounter guards and browser
throughput checks; compilation alone does not establish scientific validity.

Inventory: 9e20 kg allocated from a provisional ~3e21 kg asteroid-belt budget;
changing resolution retains total allocated mass and total actuator/storage
capacity. This is an assumed constructed orbital population, not an extraction
or composition model. Ideal central coupling reaches 2 AU; hardware/propagating
field momentum is not modeled. Controller observations/plans are light delayed.
All gravitational objects are resolved masses; there are no fake display agents,
fixed Sun, orbit clamps, free replenishment or invented drag forces.
