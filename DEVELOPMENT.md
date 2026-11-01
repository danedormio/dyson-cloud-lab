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
6. Read back merge status/commit/development SHA, observe post-merge CI and applicable Skunkworks deployment health, and checkpoint exact outcomes in Notion (durable GitHub evidence with a pending reconciliation flag if Notion is temporarily unavailable). Stop after the authorized task, except for eligible next work under the bounded daily authorization below. **Only separate explicit owner authorization for main/public production or releases** permits those actions. Changes to coupling laws, resource accounting, integrators, runtime architecture, security, charges or broad autonomous behavior still need approved task scope and applicable validation; development merge authority does not supply that scope.

## Limitations / status
- This branch provides Python REBOUND IAS15 scaffolding and tests; the production site still uses its existing JavaScript gravity-only visualization.
- Browser automation exercises actual DOM interactions using Playwright on a CI runner. Screenshot review and assertions remain necessary for visual claims.
- Do not assume a CI run exists, or has passed, until GitHub reports its outcome. The historical installation failure is superseded: the November 1 pilot ran real REBOUND locally and in CI (41 physics/API/recovery and 12 browser tests). Verify each new exact head rather than reusing that count as a fresh pass.
- Unattended operation is not established by configuration alone. GitHub Actions is a test runner; a real scheduled Codex worker, recovery and report delivery must be demonstrated before calling the daily loop operational.
- Render's production service currently deploys commits to main on push; `main` remains separately owner-authorized. Development changes use feature PRs into foundation/rebound-ci and the standing AGENTS gates. Account for the existing Skunkworks service tracking that development branch before integration. No new service, permissions or deployment configuration is authorized here.
- Existing Skunkworks already runs the Python development backend. Preserve its service and access settings; do not recreate staging or modify production routing. Verify the actually deployed commit separately from CI.


## Bounded daily development-and-review loop

This section is the existing workflow's operational contract, not proof that a
runner is working. The owner explicitly authorizes its activation and tests on
November 1, 2026. The canonical Notion Loop 2 Activation Gate records actual task,
runner, schedule, run/worker IDs, evidence and unresolved capabilities. No rival
operating guide, new paid service or reviewer account is needed.

- **Select:** resume the recorded in-progress task first. Otherwise select at
  most one open GitHub issue or checkpoint task within standing owner-authorized
  routine scope with explicit acceptance criteria. Deterministic order: recorded
  priority, then oldest issue number. No eligible work means report idle; never
  manufacture changes to fill a day. Until activation is demonstrated, scope is
  loop policy/testing/recovery/reporting only, not simulator features or research.
- **Bound:** default one active worker, 30 minutes per cycle, at most two worker
  launches and three repair iterations. Use existing Codex entitlement only; no
  paid API fallback or automatic budget increase. The runner must enforce process
  timeout and record model usage when available; prompt limits are advisory and
  must not be advertised as enforced token/dollar caps. Missing enforceable limits
  or usable credentials must be reported, not bypassed.
- **Implement/test/review:** follow AGENTS preflight, isolated branch, draft PR,
  exact-head physics/API/recovery and browser CI, screenshots where relevant and
  documented acceptance-criteria review. A routine qualifying PR may leave draft
  and merge normally into development without another owner click; respect host
  protections and consequential-action gates. Never use author-account APPROVE.
- **Persist:** before/after side effects record task/run ID, base/head/tree,
  branch/PR, changed paths, accepted actions, tests, remaining budget and next step
  in the existing GitHub issue/PR and Notion checkpoint. Local files are a cache,
  not the only durable record. Re-read an uncertain mutation before retrying it.
- **Recover:** take an exclusive per-repository lease before edits; use an atomic
  claim/lease supported by the chosen runner and refuse overlapping work. After
  interruption reconcile lease, remote refs, existing PR, source fingerprints and
  completed actions; do not recreate commits/PRs or repeat uncertain merges.
  Permit one relaunch within the remaining cycle budget, then stop and report.
  Test a real Codex worker termination/relaunch, not a dummy process or only a
  fresh checkout. Never kill an unrelated worker.
- **Report:** deliver one concise owner-facing result with completed work and
  exact SHAs/PR, tests and CI links, deployment observations, recovery outcome,
  next approved task and decisions/blockers. Report idle or failed runs too.
  Existing Notion/GitHub hold the audit trail; the runner's inbox/notification is
  the delivery path. A saved report or chat reference alone does not prove receipt.
- **Release boundary:** no `main` merge/public production deploy, new scientific
  claim/model, sensitive security/credential change, access/cost/infrastructure
  change or unapproved task. Keep existing Skunkworks policy; do not trigger a
  duplicate deploy to compensate for unverified automatic delivery.

Choose the simplest available supported scheduler with the required execution
capabilities. A cloud chat task can be tested for invocation/reporting, but must
not be called a Codex development worker if it cannot access the repository,
execute tests, publish through approved credentials and expose safe process
recovery. Prefer an already-authenticated Codex app automation on the existing
repository when cloud capabilities are insufficient; verify the installed
product's supported setup before recommending a one-time owner action. Do not
copy authentication files into an ad hoc worker home or defeat a read-only mount.

**Activation evidence required:** one clock-triggered unattended invocation,
actual implementation/test/review cycle, real worker kill/relaunch with durable
idempotent recovery, verified report delivery and continued daily scheduling.
Configuration, a manually requested run, a stopped future schedule or controlled
checkout resumption cannot individually establish those claims. Keep status
explicitly partial/blocked until every required observation exists.
