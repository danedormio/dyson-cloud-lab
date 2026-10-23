# Issue #3 verification evidence

Base: `foundation/rebound-ci` at `b6bee1b8dad0465916cc3ff06ef1219a0038b2cc`.
Implementation branch: `feat/issue-3-recoverable-sessions`.

Local environment: Python 3.12.14, REBOUND 4.6.0, pytest 9.1.1,
Playwright 1.64.1, installed Chromium 154.0.8037.57, Linux.
Dependencies installed into `/workspace/dyson-venv` because the system user
package directory is read-only. Browser download was blocked by network policy;
automated tests used the installed Chromium through Playwright, not mocked DOM.

## Baseline and repair evidence

- Baseline REBOUND: 7/7 passed.
- Baseline isolation reproduction: B had 2 bodies; A launched; B then had 3.
- Baseline browser: REBOUND interactions passed; static preview failed because
  managed Chromium blocks `file://`. Serving the unchanged preview over local
  HTTP preserves the assertions and matches how the app is deployed.
- First implementation run: 15/16 physics/API tests passed, 2/3 browser tests
  passed. API failure compared refreshed signature/expiry rather than physical
  state; its assertion now compares all physics/solver fields. Browser failure
  exposed Python/JavaScript JSON numeric spelling differences in HMAC input.
  Numeric canonicalization fixed the actual ownership-preserving UI restore.
- A targeted malformed-number probe found FastAPI's NaN validation-error
  serialization returned 500. Requests now reject non-finite/deep malformed JSON
  before parsing in the endpoint and use non-echoing validation responses.
- Repair verification: 19/19 physics/API and 3/3 browser tests passed. Subsequent
  hardening checks cover quota persistence, transaction failure and conservation.
  Final verification: **25/25 passed** (7 original REBOUND tests, 14 session/API tests, 4 Chromium tests; 9.83 seconds). No weakening of physical tolerances, disabling tests,
  force-model changes or unbounded repair loop was used.

## Measured continuation (364 simulated days)

Sun + Earth + 3 deterministic 1-kg cloud bodies. Save at day 28, then 12 times
recreate the app/store and integrate another 28 days. Compare against one live
reference integrator continued from the same day-28 state.

| Metric | Measured | Required |
| --- | --- | --- |
| Maximum position difference | 2.241e-15 AU | <1e-8 AU |
| Maximum velocity difference | 6.922e-11 m/s | <1e-4 m/s |
| Relative gravitational energy drift | 6.528e-16 | <1e-8 |
| Relative angular-momentum drift | 1.817e-16 | <1e-8 |
| Linear momentum / total mass | Assertion passed | <1e-8 m/s |
| Mass and elapsed time | Exact equality | Preserved |

Energy drift remains measured against the original scenario baseline, not a
new baseline at each reconstruction. These measurements are for this bounded
scenario and runtime, not all possible close encounters or chaotic trajectories.

## Browser evidence

Two independent cookie jars initialize distinct sessions, each launches, steps,
exports, resets and restores through the actual UI. Each rejects the other's
signed export. A real backend SIGKILL and recreation with the same SQLite file
retains A at 2 days and B at 1 day. Retrying the interrupted action reads committed
state without replaying a step. A later reset still leaves B unchanged. No page
JavaScript exceptions were observed.

![Disconnected session with explicit reconnect](evidence/issue-3-disconnected.png)

![Owner A recovered at two simulated days](evidence/issue-3-recovered.png)

These are simulator-only screenshots, without credentials or personal data.
CI produces fresh artifacts on each run. Live Render deployment and host-loss
recovery were not tested; no service was deployed or changed.

## Review and remaining limits

See [SESSIONS.md](SESSIONS.md) for storage survival, cookie ownership/expiry,
non-portable signed exports, serialized compute and ingress hardening limits.
The pre-existing coincident-body `cloud_count=8` scenario fails safely rather
than being silently clamped or changing the physics. There is no physics claim
for coupling/capture.

GitHub API access was denied by the environment proxy during development.
Do not treat configured CI jobs or local test results as proof of a GitHub CI run;
record actual CI URLs/outcomes only once accessible.
