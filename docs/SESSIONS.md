# Independent, recoverable REBOUND sessions (Issue #3 / PR #4)

## Run and configure

From the checkout root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
# Set DYSON_RECOVERY_KEY securely in the hosting service's runtime environment.
# Optional: DYSON_SESSION_DB=/existing/persistent/local/path/sessions.sqlite3
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

**One operator action is required before enabling redeploy recovery:** generate
32 random bytes as 64 hexadecimal characters and save that value securely as
`DYSON_RECOVERY_KEY` in the hosting service's environment settings. Keep a secure
copy and keep the same value across shutdowns, redeploys and replacement hosts.
Use a trusted local secret generator; do not paste the value into chat, source,
CI logs or a committed `.env` file. This must be a real runtime secret, not a
proxy placeholder. The application rejects malformed configured keys.

No paid service, external database, new account, public website, production
routing or Render deployment configuration was introduced or changed. The
owner must approve any eventual hosting configuration/deployment separately.
When the key is absent the ordinary SQLite workflow still works, but the UI
explicitly says that redeploy recovery is unavailable; it never promises it.

## How free recovery works

1. SQLite remains the live registry. Each successful operation commits the full
   world before its response. Transactions serialize updates across processes
   sharing the same local database. Failed writes return 503 and roll back.
2. The browser creates a separate random 256-bit recovery credential and keeps
   it in IndexedDB. The server binds its hash to the cookie-authenticated world.
   Each world response includes a recovery capsule authenticated with the
   deployment key: complete state, original energy baseline, scenario/solver
   metadata, owner hash, revision and expiry.
3. The browser transactionally saves that capsule after every successful action.
   “Recovery saved on this browser” appears only after IndexedDB commits it.
   Late responses cannot replace a higher-revision backup. If saving fails,
   the browser pauses and visibly reports **NOT saved**. Retry reads committed
   server state and does not repeat an uncertain step.
4. A stale/missing cookie or erased server session triggers `/api/recover` with
   the capsule and recovery credential. The server checks provenance, ownership,
   expiry and bounds, then reconstructs a private world and issues a new cookie.
   A surviving newer server row wins over an older client backup. Other owners'
   worlds are not overwritten. Nothing advances while the server is down.
5. **Private recovery backup** downloads both the capsule and recovery credential.
   Store this file somewhere safe outside the hosting service and browser.
   **Restore checkpoint**, or **Open private recovery backup** on the connection
   screen, imports it on a clean browser or another origin using the same server
   deployment key. Possession of this file grants access to that simulation.

This handles complete server database loss, not just restart of a Python process.
A fresh server needs only the application, the unchanged deployment key, and a
client's browser backup or private recovery file. SQLite's default path is
`.session-data/sessions.sqlite3`; it is not treated as durable on free Render.
The browser backup/file is the durable copy outside that ephemeral host.
Existing SQLite databases migrate additively and atomically across workers.

## Guarantees and limitations

- Recovery is to the latest **acknowledged browser backup**, or to the newer live
  SQLite state when it survives. A server may commit an action just before a
  connection loss/browser closure prevents the backup write. If the server disk
  is then erased, that unacknowledged action can be lost. It is not replayed.
- Browser storage can be cleared, evicted, unavailable in private browsing, or
  lost with the device. Keep a downloaded private recovery file independently.
  Clearing both browser data and every file backup loses the simulation.
- Losing/changing `DYSON_RECOVERY_KEY` prevents verification of old backups.
  It is not generated afresh at startup. Key rotation with old-key verification
  and account-based recovery are not implemented. Back up the key securely.
- Recovery capsules expire after 365 days. Successful mutations and periodic
  reads renew the browser copy; download an updated file before an old file
  expires. Ordinary **Save checkpoint** files remain short-lived, session-bound
  undo checkpoints, not the portable private recovery files.
- Importing a private recovery file rotates the session cookie. Another browser
  using the same recovery owner may need to reconnect. Independent owners stay
  isolated. This is capability ownership, not account login or collaborative
  synchronization. Revocation of previously downloaded private files is absent.
- Integrity/ownership are authenticated, not encrypted. Keep private files,
  IndexedDB data, cookies and the database private. A stolen credential or file
  can grant access. Local administrators and the hosting secret store are trusted.
- Use HTTPS and correctly trusted proxy scheme headers. IndexedDB and Web Crypto
  require a modern browser/secure origin; localhost is supported for development.
- Multiple workers must share the same local SQLite file. Separate distributed
  replicas, network filesystems, public-scale ingress protection and a wall-time
  CPU sandbox are outside this bounded prototype. Anonymous session creation can
  exhaust capacity; a public release still needs ingress abuse controls.

The implementation and tests do not constitute a live Render deployment test.
No paid durability or browser-vendor durability guarantee is claimed.

## Ownership, API compatibility and bounds

The normal cookie is 256-bit random, host-only, HttpOnly, SameSite=Strict,
scoped to `/api`, and Secure on HTTPS. Lookups store only its SHA-256 hash.
`POST /api/session` accepts an optional recovery credential. An existing browser
backup plus missing cookie cannot silently bootstrap and overwrite a new world.
Older API clients can continue using existing endpoints and a cookie jar.
`DELETE /api/session` forgets the cookie; old unused rows expire normally.

`GET /api/checkpoint` / `POST /api/restore` retain the short-lived per-session
signed checkpoint flow. `/api/recover` instead requires a deployment-signed
capsule **and** its independent recovery credential. A copied capsule or ordinary
checkpoint without that credential cannot recover another owner's world.
The portable private backup deliberately includes the credential for owner-
initiated transfer. Unsigned/untrusted worlds and public dataset submissions
remain disallowed. Trusted offline `CloudWorld.restore` remains available.

JSON signatures normalize numerical values across Python/browser reserialization.
Cross-site API requests and mismatched-Origin mutations are rejected; mutations
require JSON. Bounded uploads are checked before parsing, including chunked
requests. API responses are not cacheable and validation errors do not echo
credentials or uploaded worlds.

| Resource | Policy |
| --- | --- |
| Active sessions | 32; additional creation/recovery returns 429 |
| SQLite inactivity expiry | 24 hours, refreshed on successful requests |
| Ordinary checkpoint expiry | 24 hours from export |
| Recovery capsule expiry | 365 days from issue/renewal |
| Bodies | 202 total, including Sun/Earth; reset allows 0–200 cloud bodies |
| Request/checkpoint size | 262,144 bytes |
| Successful requests | 600 per owner per fixed 60-second window; recovery preserves the live quota |
| Step | Finite positive seconds, at most 30 simulated days |
| SQLite contention timeout | 10 seconds; failure returns 503 |

Expiry cleanup happens on requests. Failed operations do not extend expiry or
consume the successful-request quota. Restoring onto a genuinely empty database
starts a new quota window because that host has no retained request history.

## Physics and initial conditions

SI units, synthetic t=0 epoch, common COM frame, massive moving Sun, mutual
Newtonian gravity, IAS15 default epsilon 1e-9 and initial dt=3600 seconds remain
unchanged. No trajectory clamping, softening, new forces, coupling or capture
was added. Conservation comparisons apply between explicit launches/resets/
restores, not across addition/removal of matter.

**Scenario version 2 fixes the eight-cloud-body initialization:** cloud phases
use `(i + 0.5) * golden_angle` instead of `i * golden_angle`. Previously, for
8 clouds, the first radius was exactly 1 AU and its phase exactly zero: the
particle coincided with Earth, giving infinite potential energy. The half-step
phase offset avoids that seed degeneracy for all 0–200 supported populations.
Radii/masses/velocity rules are unchanged. Existing checkpoints retain their
actual coordinates; missing scenario version is interpreted as legacy version 1.

Both SQLite and browser recovery are state-only, not full IAS15 adaptive-history
archives. Positions, velocities, masses, labels, time and original energy
baseline survive. Repeated continuation is tested against uninterrupted
integration, not claimed bitwise-identical. Tests require position differences
<1e-8 AU, velocity differences <1e-4 m/s, relative energy/angular-momentum drift
<1e-8 and momentum divided by total mass <1e-8 m/s over 364 simulated days.
Rerun continuation tests after changing the solver/version.

## Verification

```sh
python -m pytest tests/test_rebound.py tests/test_sessions.py tests/test_recovery.py -v -s
python -m playwright install chromium
python -m pytest tests/test_browser.py -v
# Installed-browser alternative when downloads are blocked:
DYSON_CHROMIUM_EXECUTABLE=/usr/bin/chromium python -m pytest tests/test_browser.py -v
```

Tests use temporary databases, real REBOUND, backend subprocesses and Chromium.
They cover all initial populations, conservation, migration, ownership, limits,
process kill, full database deletion, cookie loss, private-file import in a
clean browser, late responses and browser storage failure. Screenshots are in
`test-artifacts/` and uploaded by CI. Test deployment keys are random, ephemeral,
never production secrets. See [measured evidence](ISSUE-3-EVIDENCE.md).
