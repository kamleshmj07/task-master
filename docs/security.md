# Security

What the app does to stay safe, what the production host must add, and the
known shortcomings to revisit.

## In the API

- **Accounts.** Passwords are 12 to 128 characters and may not contain the
  email name. Changing the email or password needs the current password, and
  a password change logs the account out everywhere. Deleting the account
  needs the password too.
- **Sessions.** Opaque access tokens last 15 minutes. Refresh tokens rotate
  on every use, and reusing an old one revokes its whole family. The web keeps
  the refresh token in an `HttpOnly`, `Secure`, `SameSite=Strict` cookie
  scoped to `/auth/web`, and the access token in memory only.
- **Login throttling.** Per account, a backoff from 1 to 15 minutes after a
  few failures. Per IP, 20 failures per 15 minutes. Accounts are tracked by a
  hash of the email, so the throttle never reveals which emails exist.
- **Rate limits.** Auth endpoints: 5 a minute per client. Everything else
  except `/health`: 300 reads and 120 writes a minute per session (per IP when
  signed out). Every request also counts against its IP (600 a minute), so
  sending a made-up token per request cannot dodge the limits. Over a limit
  the API answers 429 with `Retry-After`.
- **Headers on every response.** `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none';
  frame-ancestors 'none'`, `Referrer-Policy: no-referrer`,
  `Cache-Control: no-store`, `Cross-Origin-Opener-Policy: same-origin`,
  `Permissions-Policy` (no camera, microphone or location). In production
  also `Strict-Transport-Security: max-age=31536000; includeSubDomains`.
- **Production surface.** No `/docs` and no `/openapi.json`. The app refuses
  to start in production unless every CORS origin is HTTPS and the auth
  secret has at least 32 characters.
- **Data access.** Every row is looked up through its owner; other users'
  rows are 404. Queries are parameterized through SQLAlchemy.
- **Logs.** JSON lines on stderr from the `task_master` loggers. Refused
  requests (401, 403, 422, 429), failed logins, lockouts, refresh-token reuse
  and refused credential changes are logged. Clients appear only as hashes;
  emails, passwords, tokens and raw IPs are never logged.
- **CI.** `pip-audit`, `npm audit --audit-level=high`, and Ruff's bandit
  rules (`S`) run on every push and pull request.

## What the production host must provide

- **HTTPS only**, with HTTP redirected.
- **Web and API on the same site** (for example `app.example.com` and
  `api.example.com`), or the `SameSite=Strict` refresh cookie is not sent.
- **`TASK_MASTER_TRUSTED_PROXIES`** set to the load balancer's addresses, so
  rate limits and the login throttle see the real client IP. Without it every
  request appears to come from the proxy, and one client's failures would
  lock everyone out.
- **A request body size limit** at the proxy (1 MB is plenty).
- **These headers on the web app's files** (the API sets its own):

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' https://api.example.com; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

Replace `https://api.example.com` with the real API origin. The production
build has no inline scripts, so `script-src 'self'` holds. This CSP cannot
go in `index.html` as a meta tag: `frame-ancestors` only works as a header,
and the Vite dev server needs inline scripts.

## Known shortcomings (revisit before launch)

1. **One API process only.** Rate limits and the login throttle keep their
   counters in memory. To stop two processes from silently doubling the
   limits, production holds a Postgres advisory lock and a second process
   refuses to start (`single_process.py`). Moving the counters to Redis lifts
   this cap.
2. **Zero-downtime deploys may fail because of (1).** Many hosts start the
   new version before stopping the old one. The old process still holds the
   lock, so the new one refuses to start. When choosing a host, either make
   deploys stop the old version first, or change the new process to wait for
   the lock instead of quitting.
3. **Password reset and email verification** need an email provider, which
   is not chosen yet.
4. **Registration reveals whether an email is taken** ("An account with this
   email already exists"). Fixing it properly needs email: sign-up would then
   always say "check your inbox". Rate limits slow down anyone probing.

## Security review (2026-11-24)

Whole-app review on `feature/security-hardening`. Fixed:

- Email and password changes did not need the current password.
- API-wide rate limits were missing; a made-up token per request could also
  have dodged per-session limits, so every request now counts per IP too.
- Behind a proxy every client would share one IP for limits and throttling.
- No security headers; the OpenAPI schema was public in production;
  production could start with HTTP CORS origins or a short secret.
- A finished task's steps were read-only only in the web app; the API now
  refuses changes too.
- Top 3 plans could be saved for any date up to 9999; now at most a year
  ahead.

Checked and fine: ownership on every route (other users' rows are 404),
parameterized queries, no secrets in the repository, Postgres bound to
localhost, registration cannot set `is_superuser` or `is_verified`, access
tokens kept in memory on the web, no `dangerouslySetInnerHTML` or `eval`,
refresh cookie scoped and `SameSite=Strict`.
