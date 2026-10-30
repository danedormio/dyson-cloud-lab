# Dyson Cloud Laboratory — instructions for coding agents

## Product and mission
Build a **gamified citizen-science future-civilization design sandbox**. A common physics core powers playful scenarios, education and reproducible scientific experiments, from Earth–Moon clouds to solar systems and aggregated galactic networks. Multiple players may eventually contribute research; a game result is not a scientific finding until validated.

## Current repository state
- Production `main` powers the canonical public URL https://dyson-cloud-lab.onrender.com. Its current frontend is the old gravity-only static preview, NOT REBOUND.
- `foundation/rebound-ci` contains the experimental REBOUND IAS15 Python backend in `physics.py`, FastAPI in `server.py`, frontend `rebound.html`, physics tests in `tests/test_rebound.py`, and browser tests in `tests/test_browser.py`.
- Separate experimental Render service presently uses the development branch; its service display name is `dyson-cloud-lab-skunkworks`. Its assigned onrender URL may still contain `rebound-staging`.
- All code modifications require a development branch and a pull request; **never commit directly to `main` or merge/deploy production without explicit owner approval**.
- Prefer extending existing interfaces over standalone competing demos or creating additional user-facing URLs.

## Mandatory preflight — before every coding task
The approved [Notion development roadmap](https://app.notion.com/p/40104771655d8195b3b3f2d1b8816e8d), [five-loop charter](https://app.notion.com/p/40204771655d81b39eadfcc8ba50e5c9), and [development activation gate](https://app.notion.com/p/40404771655d8153be75c65a24bfc176) govern scope and owner approvals. Read the current approved assignment; historical repository prose is not new authorization.

1. Verify the repository identity and current authoritative remote `foundation/rebound-ci` head through supported Git transport or the GitHub plugin. Record the exact base SHA for this task; never assume a remembered SHA is current.
2. Inspect and report the local checkout path, origin, branch, HEAD, tracked/untracked changes and relationship to that remote head. Fetch required history and use an isolated feature branch from the verified base. Preserve unrelated work; never overwrite a dirty tree, force-push, or copy an old `main` snapshot into a development PR.
3. Verify read **and write** publication capability before modifying files. A successful read or permission listing is insufficient: create and read back the isolated branch at the base SHA using the intended supported method. Confirm that method supports commits and draft PRs; verify the resulting commit and PR when publishing. If shell Git is unavailable, a GitHub-plugin workflow may preserve the verified remote parent/tree, fetch files by immutable SHA, verify blob identities, commit only intended paths, and read back the branch, commit and PR. Report any local snapshot/history gaps; do not call a partial snapshot a synchronized Git checkout.
4. **Fail closed:** if the base, synchronization, cleanliness or publication path cannot be verified, stop before edits and report the exact blocker and safe resumption step. A stale local checkout must first be synchronized safely or excluded from implementation in favor of the verified plugin workflow. Do not guess remote state, weaken checks, bypass the managed proxy/sandbox, expose credentials, change permissions or silently switch to production.
5. Recheck the remote base before publication and disclose any movement; reconcile and rerun affected checks before claiming current-base validation. On resume, repeat preflight and reconcile existing branch/PR state before retrying writes. Checkpoint approved scope, base/head SHAs, changed paths, checks, blockers, retry budget and next action in Notion; default to at most three repair iterations.
6. Open a **draft PR targeting `foundation/rebound-ci`**, never `main`. Verify physics/API/recovery and browser Actions runs identify the exact PR head SHA; distinguish GitHub's synthetic merge checkout SHA when applicable. Report every pass, failure, skip and test not run, with CI links. Apply the development integration gates below before merging; an assignment requiring review-only publication stays unmerged. A green run does not prove scientific validity.
7. Every task report must include approved scope, base SHA, final head SHA, changed files, tests/checks and their outcomes, limitations, synchronization method and PR URL, plus merge/development SHA and post-merge observations if integrated. Record evidence in the existing Notion task/activation record and report the outcome to the owner. Stop after the approved task; do not activate schedules or begin a new assignment.

`main`, public releases, the public production deployment and deployment configuration remain protected by separate explicit owner approval. Green CI alone does not authorize integration, deployment, permissions, costs or scientific scope expansion. Standing development merge authority is limited to the gates below; it does not enable GitHub auto-merge, unattended scheduling or parallel autonomous agents.

## Development integration — standing owner authorization (2026-10-30)
The [standing owner authorization](https://app.notion.com/p/40404771655d8153be75c65a24bfc176) permits Codex to merge **its own qualifying PRs into `foundation/rebound-ci`** without individual owner merge approval, only for previously authorized tasks. Task approval, scope and scientific acceptance remain separate from integration eligibility. A narrower assignment overrides this default: **this policy-transition PR must remain unmerged for owner review**.

Before each development merge:
1. Repeat current-assignment/AGENTS/remote-state verification. Inspect the actual diff and confirm only authorized changes, target `foundation/rebound-ci`, and no effects on `main`, production release configuration, permissions, secrets/private data, costs or unapproved services.
2. Preserve required peer or automated independent scrutiny and all configured protection/review checks. Critically review the diff; self-reported success is not independent test evidence and standing authority is not permission to self-approve or bypass a required review.
3. Require relevant exact-head physics/API/recovery and browser CI passes with zero unexplained failures or skips. Pass applicable security, scientific-model validation and migration/regression gates at documented thresholds; software CI alone does not validate a physical model. Record test checkout SHA separately when GitHub uses a synthetic merge.
4. Reconcile concurrent base movements and prior PRs without force or protection bypass. Rerun affected checks on the reconciled head; earlier green results do not validate a changed head or repair formerly failed PRs retroactively.
5. Disclose effects on the existing Skunkworks development deployment, which tracks this branch. If integration triggers auto-deploy, verify its effects stay within the previously approved development environment, with no new paid resources or private-data exposure. Uncertain or out-of-policy deployment effects block merging; do not alter hosting configuration to make a PR eligible.
6. Use the normal GitHub-supported merge method after all gates pass (transition out of draft only when eligible). Respect host/tool safety blocks; never retry a blocked merge through an alternate API or change protections to evade it. Read back merged status, merge commit and current development SHA; observe post-merge CI and deployment health as applicable, and record outcomes or unresolved observations.
7. Persist scope, diff/review evidence, exact SHAs, checks, merge/deployment effects and safe resumption in the existing Notion checkpoint. If Notion is temporarily unavailable, retain durable GitHub PR/commit evidence, flag reconciliation as pending and do not claim it was written.

Fail closed for failing/unexplained checks, scope deviations, substantial new model assumptions or known validation deficiencies, security/privacy/license risks, costs, force/bypass requirements, permissions, new services or public exposure: stop and seek an explicit owner decision. Standing authority never authorizes `main` integration, public production changes/releases, recurring unattended scheduling or parallel autonomous agents. Report integration or a review-ready/blocked PR and stop; do not select a new task automatically.

## Physical invariants — non-negotiable
1. The Sun, Earth, Moon, other planets, cloud elements and incoming bodies are ordinary massive simulation objects. The Sun is NOT pinned; track back reaction. Appearance and packet/cloud labels are views, not physics species.
2. REBOUND governs resolved Newtonian N-body gravity. Document units, reference frames, epoch, numerical accuracy and solver configuration. Preserve mass, linear/angular momentum and total energy with all physically applicable reservoirs (photons, expelled matter, stored energy, heat) when coupling/actuation is introduced.
3. A force or control law is not automatically physically feasible. A non-gravitational impulse must identify counterpart or exported momentum and energy source, enforce force/power/heat limits and supply conservation tests.
4. Protect important orbits via **monitored constraints and physically funded control**; never fake orbit stability by clamping planetary trajectories.
5. For coarse-grained interstellar/galactic scales, preserve conservation contracts and document approximation errors across resolution boundaries. Do not claim one particle per star or perfect individual-body resolution.
6. Keep quantitative research findings reproducible with versioned scenario, initial state, random seed, algorithm settings, diagnostics and code revision. Flag unvalidated claims.

## Autonomous iteration loop
1. Pick only a user-approved issue/scope. State acceptance criteria, numerical tolerances and explicit out-of-scope behavior.
2. Inspect current implementation and reproduce the failure or establish a measured baseline before changing the code.
3. Make the smallest coherent implementation that meets the task; you may do substantial code work where acceptance tests justify it. Keep architecture modular.
4. Run `python -m pip install -r requirements.txt`, `python -m pytest tests/test_rebound.py -v`, `python -m playwright install chromium`, `python -m pytest tests/test_browser.py -v`. Use GitHub Actions CI and inspect failure logs/screenshots.
5. Inspect actual browser interactions and visual output: simulate a real user, not just load the page. If relevant, capture screenshots and compare to an approved baseline.
6. Retry boundedly (pilot default: at most **3 code-repair iterations**); if blocked, report evidence rather than silently weakening tests or falsifying validation.
7. Prepare a draft PR stating task objective, files changed, CI links, scientific assumptions, before/after metrics, screenshots, known limitations and remaining risks. Integrate only under the standing development gates above; keep review-only or ineligible PRs unmerged and report the needed owner decision.

## Security, ownership and usage constraints
- No secrets, personal data or Notion private contents in GitHub source, CI logs, public datasets or browser snapshots. The repo and both Render websites may be public.
- Never spend money, upgrade hosting plans, create user accounts, publish datasets, alter access permissions, set auto-merge, change licensing/IP terms, or activate persistent bots without an explicit scoped approval.
- **Do not modify production routing or Render deployment configuration without approval.**
- No dependency-license assumptions: REBOUND's GPL-3.0 obligations require review before distributed/commercial app licensing; maintain attribution and upstream notices.
- Free-tier backend can sleep. Design clear readiness polling and saved-state recovery; persistent multiuser simulations require session isolation and durable storage. Do not assume one shared process is safe for multiple user sessions.
- Protect experiment datasets against malicious submissions and unbounded compute; implement quotas and validation before opening public write APIs.

## Done means
Tests pass on a real REBOUND install and automated Chromium; reproducible scenario evidence supplied; preservation of physics invariants demonstrated for modified subsystems; no unexplained regressions. The owner receives a reviewable PR and exact evidence: either verified development integration under the standing gates, or an explicitly unmerged review-only/blocked PR. Passing tests alone authorize no public release or production deployment.
