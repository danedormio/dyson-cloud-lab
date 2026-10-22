# Dyson Cloud Laboratory — instructions for coding agents

## Product and mission
Build a **gamified citizen-science future-civilization design sandbox**. A common physics core powers playful scenarios, education and reproducible scientific experiments, from Earth–Moon clouds to solar systems and aggregated galactic networks. Multiple players may eventually contribute research; a game result is not a scientific finding until validated.

## Current repository state
- Production `main` powers the canonical public URL https://dyson-cloud-lab.onrender.com. Its current frontend is the old gravity-only static preview, NOT REBOUND.
- `foundation/rebound-ci` contains the experimental REBOUND IAS15 Python backend in `physics.py`, FastAPI in `server.py`, frontend `rebound.html`, physics tests in `tests/test_rebound.py`, and browser tests in `tests/test_browser.py`.
- Separate experimental Render service presently uses the development branch; its service display name is `dyson-cloud-lab-skunkworks`. Its assigned onrender URL may still contain `rebound-staging`.
- All code modifications require a development branch and a pull request; **never commit directly to `main` or merge/deploy production without explicit owner approval**.
- Prefer extending existing interfaces over standalone competing demos or creating additional user-facing URLs.

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
7. Prepare an **unmerged** PR stating task objective, files changed, CI links, scientific assumptions, before/after metrics, screenshots, known limitations and remaining risks. Ask owner for approval.

## Security, ownership and usage constraints
- No secrets, personal data or Notion private contents in GitHub source, CI logs, public datasets or browser snapshots. The repo and both Render websites may be public.
- Never spend money, upgrade hosting plans, create user accounts, publish datasets, alter access permissions, set auto-merge, change licensing/IP terms, or activate persistent bots without an explicit scoped approval.
- **Do not modify production routing or Render deployment configuration without approval.**
- No dependency-license assumptions: REBOUND's GPL-3.0 obligations require review before distributed/commercial app licensing; maintain attribution and upstream notices.
- Free-tier backend can sleep. Design clear readiness polling and saved-state recovery; persistent multiuser simulations require session isolation and durable storage. Do not assume one shared process is safe for multiple user sessions.
- Protect experiment datasets against malicious submissions and unbounded compute; implement quotas and validation before opening public write APIs.

## Done means
Tests pass on a real REBOUND install and automated Chromium; reproducible scenario evidence supplied; preservation of physics invariants demonstrated for modified subsystems; no unexplained regressions; human receives a reviewable **unmerged** PR. A passing test is NOT approval to deploy.
