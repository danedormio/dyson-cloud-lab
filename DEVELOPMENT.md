# AI-assisted development process — approved tasks, gated integration

The owner's standing development merge authorization (2026-10-30) is implemented in [AGENTS.md](AGENTS.md#development-integration--standing-owner-authorization-2026-10-30). It permits Codex to merge its own qualifying PRs into `foundation/rebound-ci` for previously approved tasks without a separate owner merge click. All integration gates there apply; task scope and production/public release approval remain separate. Review-only PRs remain unmerged until their specifically required review and authorization are complete.

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
5. Review the actual diff, exact-head physics/API/recovery and browser CI, screenshots and applicable model/security/migration evidence. Routine low-risk authorized work may use documented automated acceptance-criteria review and independent exact-head CI; no universal second-person/account approval is required. Preserve all configured review/protection checks. Reconcile concurrent base movements; verify Skunkworks auto-deploy effects remain inside the previously approved development environment without new costs or private-data exposure. Codex may merge its own eligible development PR through normal GitHub methods only after every AGENTS integration gate passes. Review-only assignments stay unmerged; unresolved gates require an owner decision. No self-approval, force, protection bypass or alternate route around a safety block.
6. Read back merge status/commit/development SHA, observe post-merge CI and applicable Skunkworks deployment health, and checkpoint exact outcomes in Notion (durable GitHub evidence with a pending reconciliation flag if Notion is temporarily unavailable). Continue only within the authorized milestone; stop after usable delivery and wait for owner feedback. **Only separate explicit owner authorization for main/public production or releases** permits those actions. Changes to coupling laws, resource accounting, integrators, runtime architecture, security, charges or broad autonomous behavior still need approved task scope and applicable validation; development merge authority does not supply that scope.

## Limitations / status
- This branch provides Python REBOUND IAS15 scaffolding and tests; the production site still uses its existing JavaScript gravity-only visualization.
- Browser automation exercises actual DOM interactions using Playwright on a CI runner. Screenshot review and assertions remain necessary for visual claims.
- Do not assume a CI run exists, or has passed, until GitHub reports its outcome. The historical installation failure is superseded: the November 1 pilot ran real REBOUND locally and in CI (41 physics/API/recovery and 12 browser tests). Verify each new exact head rather than reusing that count as a fresh pass.
- Unattended operation is not established by configuration alone. GitHub Actions is a test runner; supported execution, checkpoint recovery and delivery must be demonstrated before claiming autonomous milestone completion. Daily selection is superseded below.
- Render's production service currently deploys commits to main on push; `main` remains separately owner-authorized. Development changes use feature PRs into foundation/rebound-ci and the standing AGENTS gates. Account for the existing Skunkworks service tracking that development branch before integration. No new service, permissions or deployment configuration is authorized here.
- Existing Skunkworks already runs the Python development backend. Preserve its service and access settings; do not recreate staging or modify production routing. Verify the actually deployed commit separately from CI.


## Owner-directed milestone workflow

The owner superseded daily development on November 1, 2026. The old daily
schedule is disabled, with history retained in the canonical Notion checkpoint.
No new milestone or recurring work selection is authorized by this document.

Within an expressly authorized milestone, plan coherent tasks internally and
continue implementation, tests, debugging, acceptance review and qualifying
integration until there is a usable result. A merged PR or a trigger is not the
completion criterion. Do not ask for routine per-task approval or stop after an
incidental small success. Preserve AGENTS exact-head CI and consequential gates.

Use the attached execution environment directly. Do not launch nested Codex
workers to evade platform constraints. Across supported sessions, recover scope,
base/head/tree, branch/PR, changed files, tests, remaining runtime/retry budget and
next action from the existing Notion checkpoint and GitHub evidence. Reconcile
remote state and uncertain mutations before retrying; preserve owner work and
avoid duplicate commits/PRs. Never claim background execution without an actual
supported running mechanism. If continuation cannot be arranged, checkpoint the
precise platform limit and smallest resumption action rather than invent progress.

Use bounded commands and reasonable milestone budgets: record an active-work
target (initial playable milestone: 90 minutes) and at most three repairs per
coherent subsystem before reassessing. Budgets carry across interruption. No paid
API fallback, hosting upgrade, new account or expense without explicit approval.
Prompt runtime/usage targets are advisory unless enforcement is actually known.
Keep status and completion claims proportional to the observed evidence.

Deliver a working development URL or straightforward launch method, usable
experiments, exact commit/PR/CI evidence, physical limitations and the next
substantial recommendation. Keep routine technical records in GitHub/Notion;
owner messages should focus on meaningful results or consequential blockers.
After delivery, stop initiating development and wait for feedback. Production,
scientific architecture, security-sensitive actions and costs retain owner gates.

### Checkout evidence and supported continuation

Use the existing cloud task directly; do not launch a nested CLI
worker. Recover the canonical Notion checkpoint and verify the current remote
branch with GitHub before trusting any local files. Then run:

```sh
python scripts/checkout_preflight.py --directory . --expected-sha FULL_REMOTE_SHA
```

The standard-library command emits JSON and exits nonzero for an unexpected
origin/commit, tracked or untracked changes, or failed Git inspection. It changes
no files or refs and never reports a credential-bearing remote. This is local
checkout evidence, not remote authentication or a repository lock. Run it before
edits and on resumption; use the checkpointed feature SHA for an existing PR,
then reconcile its ancestry with the freshly observed development branch.
A failure preserves owner work: stop and reconcile, never clean or reset it.

The existing task returns milestone results to the same chat. Its historical
schedule/run evidence lives in the canonical activation checkpoint; null API
history/receipt fields are not proof of execution or owner receipt. Recover an
existing PR before creating anything, and after a merge report the same merge
SHA on resumption without repeating the change. Direct turn continuation
has been tested; real worker kill/restart and hard per-turn model usage limits
remain unverified. Command timeouts do not enforce a whole-turn budget.
