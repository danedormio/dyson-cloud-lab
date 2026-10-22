# AI-assisted development process — approval-gated

## Desired architecture
- REBOUND IAS15 owns **one physical N-body world**: Sun, Earth, planets, clouds, tracked incoming objects. Sun moves under the same mutual gravity rules as everything else.
- Object mass is a parameter; default cloud elements are 1 kg, the Sun and Earth are assigned realistic masses. A tracked label is not a separate physics class.
- Actuation/coupling, secure orbit selection, power/heat/impulse budgets and cooperative optimization are independent subsystems to be added on top of REBOUND and separately verified. No non-gravitational forces are currently enabled in the new backend.
- Begin with Sun+Earth+bodies and progressively add planets and ephemerides, not all catalogs in the first milestone.
- A single, permanent Render URL remains the production target.

## Iteration protocol
1. Agent proposes a small hypothesis/feature and acceptance tests in an issue or PR.
2. Agent makes changes on a branch; never changes production main as an incidental side effect.
3. CI installs REBOUND and validates reference gravitational orbits, momentum and energy. Playwright drives a real Chromium browser, captures screenshots and rejects JavaScript errors.
4. Agent examines failing runs, makes bounded fixes and reruns tests. No representation that tests pass until a verified result exists.
5. Human approval gate: review code diff, CI, screenshots and new physics assumptions. **Only an explicitly approved merge to main** may update the public deployment. Changes to coupling laws, resource accounting, integrators, runtime architecture, security, charges or broad autonomous behavior require explicit approval.
6. Post-merge verify the actual Render deployment and live browser regression; revert using Git history if production fails.

## Limitations / status
- This branch provides Python REBOUND IAS15 scaffolding and tests; the production site still uses its existing JavaScript gravity-only visualization.
- Browser automation exercises actual DOM interactions using Playwright on a CI runner. It is **not** evidence of visual correctness without screenshot review and assertions.
- Do not assume a CI run exists, or has passed, until GitHub reports its outcome. REBOUND could not be installed in the current local container due DNS restrictions; GitHub CI can attempt installation.
- No autonomous always-on coding agent has been configured. GitHub Actions is an automated test runner, not an open-ended self-improving researcher.
- Render's production service currently deploys commits to main on push. Keep new changes on branches with PR reviews pending explicit user approval.
- Before switching Render to REBOUND backend, create a separate staging Python web service and test the API + UI end-to-end.
