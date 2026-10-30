# AI-assisted development process — approved tasks, gated integration

The owner's standing development merge authorization (2026-10-30) is implemented in [AGENTS.md](AGENTS.md#development-integration--standing-owner-authorization-2026-10-30). It permits Codex to merge its own qualifying PRs into `foundation/rebound-ci` for previously approved tasks without a separate owner merge click. All integration gates there apply; task scope and production/public release approval remain separate. This policy-transition PR is review-only and must remain unmerged.

## Desired architecture
- REBOUND IAS15 owns **one physical N-body world**: Sun, Earth, planets, clouds, tracked incoming objects. Sun moves under the same mutual gravity rules as everything else.
- Object mass is a parameter; default cloud elements are 1 kg, the Sun and Earth are assigned realistic masses. A tracked label is not a separate physics class.
- Actuation/coupling, secure orbit selection, power/heat/impulse budgets and cooperative optimization are independent subsystems to be added on top of REBOUND and separately verified. No non-gravitational forces are currently enabled in the new backend.
- Begin with Sun+Earth+bodies and progressively add planets and ephemerides, not all catalogs in the first milestone.
- A single, permanent Render URL remains the production target.

## Iteration protocol
1. Owner authorizes a bounded task; agent records its acceptance tests, scope and stopping conditions in an issue/task checkpoint. A proposed task is not approval to start.
2. Agent makes changes on a branch; never changes production main as an incidental side effect.
3. CI installs REBOUND and validates reference gravitational orbits, momentum and energy. Playwright drives a real Chromium browser, captures screenshots and rejects JavaScript errors.
4. Agent examines failing runs, makes bounded fixes and reruns tests. No representation that tests pass until a verified result exists.
5. Review the actual diff, exact-head physics/API/recovery and browser CI, screenshots and applicable model/security/migration evidence. Preserve independent scrutiny and all configured review/protection checks. Reconcile concurrent base movements; verify Skunkworks auto-deploy effects remain inside the previously approved development environment without new costs or private-data exposure. Codex may merge its own eligible development PR through normal GitHub methods only after every AGENTS integration gate passes. Review-only assignments stay unmerged; unresolved gates require an owner decision. No self-approval, force, protection bypass or alternate route around a safety block.
6. Read back merge status/commit/development SHA, observe post-merge CI and applicable Skunkworks deployment health, and checkpoint exact outcomes in Notion (durable GitHub evidence with a pending reconciliation flag if Notion is temporarily unavailable). Stop after the approved task. **Only separate explicit owner authorization for main/public production or releases** permits those actions. Changes to coupling laws, resource accounting, integrators, runtime architecture, security, charges or broad autonomous behavior still need approved task scope and applicable validation; development merge authority does not supply that scope.

## Limitations / status
- This branch provides Python REBOUND IAS15 scaffolding and tests; the production site still uses its existing JavaScript gravity-only visualization.
- Browser automation exercises actual DOM interactions using Playwright on a CI runner. It is **not** evidence of visual correctness without screenshot review and assertions.
- Do not assume a CI run exists, or has passed, until GitHub reports its outcome. REBOUND could not be installed in the current local container due DNS restrictions; GitHub CI can attempt installation.
- No autonomous always-on coding agent has been configured. GitHub Actions is an automated test runner, not an open-ended self-improving researcher.
- Render's production service currently deploys commits to main on push; `main` remains separately owner-authorized. Development changes use feature PRs into foundation/rebound-ci and the standing AGENTS gates. Account for the existing Skunkworks service tracking that development branch before integration. No new service, permissions or deployment configuration is authorized here.
- Before switching Render to REBOUND backend, create a separate staging Python web service and test the API + UI end-to-end.
