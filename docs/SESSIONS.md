# Independent REBOUND sessions (Issue #3)

## Run and storage contract

Start from the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
# Optional: point at an EXISTING persistent local filesystem you administer.
# export DYSON_SESSION_DB=/path/to/persistent/sessions.sqlite3
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

The default database is `.session-data/sessions.sqlite3`, ignored by Git.
No external database, account, paid service, production routing, or deployment
configuration is introduced. Newly created database directories/files use
0700/0600 permissions. The file contains private worlds and signing keys:
do not commit, publish, log or serve it with a directory-listing static server.
Use the FastAPI server for this branch.

A successful operation commits its complete checkpoint before responding.
SQLite transactions serialize operations, including requests from different
workers using the **same local database file**, preventing lost updates and
cross-owner changes. A failed operation or failed commit rolls back; the last
committed checkpoint remains authoritative. Health checks verify database
readability; a write failure returns 503 rather than acknowledging a mutation.
No simulation steps run in the background. Wall-clock downtime never becomes
simulated elapsed time. The browser pauses after a failed/uncertain action,
then reconnects to read committed state, without replaying the action.

Process termination/recreation is recoverable **only if the database file
survives and the browser retains its cookie**. Render's ephemeral filesystem
may survive sleep/process restarts but is NOT a durable-volume guarantee:
redeploys, filesystem loss, cookie deletion, or expiry can lose access. No
Render configuration is changed or persistent disk purchased here. An operator
must provide persistent storage before promising recovery across host loss.
Separate replicas without a shared local SQLite file are unsupported; network
filesystems and horizontally distributed databases are outside this task.

## Ownership and checkpoint policy

- A 256-bit random bearer cookie authenticates one world. It is HttpOnly,
  SameSite=Strict, host-only, scoped to `/api`, and Secure when served over HTTPS.
  Production use requires HTTPS and correctly trusted proxy scheme headers.
  Database lookup uses the SHA-256 hash, never a user-chosen object ID.
- `POST /api/session` bootstraps/resumes a session. Existing endpoint paths and
  payloads remain usable with a cookie jar; a missing cookie lazily creates a
  private session for older API clients. Unknown/malformed/stale cookies return
  401; they never select another world or silently overwrite a saved world.
- `DELETE /api/session` explicitly forgets the browser credential. The old row
  expires normally. The UI offers this only after a 401; it cannot recover an
  expired or lost database. Tabs sharing a browser context share a session;
  independent browser contexts have separate sessions.
- `GET /api/checkpoint` exports a version-1 state plus owner hash, expiry and
  HMAC-SHA256 signature using a per-session key kept exclusively in the database.
  `POST /api/restore` accepts only authentic, unexpired checkpoints for the
  currently authenticated owner. Reset does not change ownership or signing key.
  Exports are deliberately not portable to another browser/session.
- HMAC canonicalization normalizes JSON numbers to IEEE doubles so a legitimate
  browser JSON.parse/stringify round trip does not invalidate the signature.
  No arbitrary unsigned checkpoint import or public dataset-submission API is
  enabled. Legacy unsigned exports/localStorage caches are not automatically
  imported: they have no ownership proof. Scientific/offline `CloudWorld.restore`
  remains available for trusted local workflows.
- No CORS grants are added. Cross-site browser API requests and mismatched Origin
  mutations are rejected. Mutations require JSON. Responses are not cacheable;
  validation errors do not echo uploaded data or credentials. TLS, checksums and
  package verification remain enabled throughout installation.

This is capability ownership, not accounts: possession of a stolen cookie gives
access, and there is no account-based recovery or sharing. Protect the database
and cookies; HMAC does not encrypt checkpoint contents. Local administrators
with database access are trusted. User-chosen session IDs, sharing links,
passwords, cross-device transfers, and hostile public-scale traffic are out of
scope.

## Explicit bounds

| Resource | Default policy |
| --- | --- |
| Active sessions | 32; additional creation returns 429 |
| Inactivity lifetime | 24 hours, refreshed on successful API requests |
| Export lifetime | 24 hours from export; does not extend on later requests |
| Bodies | 202 total, including Sun/Earth and incoming bodies; reset allows 0–200 cloud bodies |
| Checkpoint/request body | 262,144 bytes, enforced before parsing even for chunked uploads |
| Successful session requests | 600 per fixed 60-second window, persisted across workers/restarts |
| One step | Positive finite seconds, at most 30 simulated days |
| Storage contention | 10-second SQLite lock timeout; failure returns 503 |

Expiry cleanup happens transactionally on requests, with no always-on bot.
Failed operations do not extend expiry or consume the successful-request quota.
All integration is serialized at database scope. The small bounds favor safety
and consistency over throughput; this is not a distributed multiplayer service.
Anonymous session creation can exhaust the finite capacity; a public release
needs ingress connection/rate/body-timeout controls, monitoring and abuse
policy. A wall-time CPU sandbox and per-account/IP quotas are not provided here.

## Physics and reproducibility

The force model, massive moving Sun, SI units, COM initial frame, ideal circular
Earth initial condition, and IAS15 integrator are unchanged. Epoch t=0 is a
synthetic scenario, not an observed ephemeris. Seeding is deterministic (no RNG).
Checkpoints retain every mass, position, velocity, role, name, time, solver/version
metadata, and original energy baseline. Persisting that baseline prevents each
restart from disguising accumulated drift. Launch adds a new ordinary massive
1-kg initial-condition body; conservation comparisons apply between explicit
launch/reset/restore events, not across the addition/removal of matter.

Storage is **state-only**, not a REBOUND Simulationarchive with IAS15 internal
adaptive history. Each API operation reconstructs a new solver in SI units,
IAS15 default accuracy (epsilon 1e-9), and initial dt=3600 seconds. Subsequent
integration is tested for accuracy, not bitwise trajectory equivalence to an
uninterrupted solver. Full integrator-history restoration might improve exact
repeatability, but introduces format/version/storage concerns and is deferred.
Rerun numerical continuation tests after any solver/version change.

The 364-day Sun/Earth + 3 cloud-body comparison against uninterrupted integration
requires maximum position error <1e-8 AU, velocity error <1e-4 m/s, relative energy
and angular-momentum drift <1e-8, and total momentum/system-mass <1e-8 m/s.
No assertions or original conservation tolerances were relaxed.

Known pre-existing scenario defect: `CloudWorld(8)` seeds its first cloud body
exactly at Earth's position, producing non-finite gravitational energy. This
change rejects that reset atomically (422) and retains the prior world instead
of persisting invalid data. Fixing that initial-condition generator is a separate
physics change; default 72 and tested 0/1/3/199/200-body scenarios are supported.
Coupling, capture, Moon/other planets and observed ephemerides remain out of scope.

## Reproduce verification

```sh
python -m pytest tests/test_rebound.py tests/test_sessions.py -v -s
python -m playwright install chromium
python -m pytest tests/test_browser.py -v
```

Where browser downloads are prohibited but Chromium is installed:

```sh
DYSON_CHROMIUM_EXECUTABLE=/usr/bin/chromium python -m pytest tests/test_browser.py -v
```

Tests isolate databases in temporary directories and start actual backend
subprocesses. Browser tests use independent contexts, actual UI checkpoint
download/upload, cross-owner rejection, a SIGKILL, reconnect/reload and further
isolated mutation. They save screenshots under `test-artifacts/`. CI uploads
that directory and runs on PRs targeting `foundation/rebound-ci` as well as main.
See [the measured evidence](ISSUE-3-EVIDENCE.md).
