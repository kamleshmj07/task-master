# Deploying Task Master on Vercel

A step-by-step guide, written on 2026-11-25. Start on a free Vercel address
(for example `https://task-master.vercel.app`) and add your own domain later
without code changes. Read it once end to end before starting. Steps marked
**(code)** are changes to make in the repo first, on a branch; everything
else is clicks and settings.

## The shape of it

```
                 https://task-master.vercel.app        (one Vercel project)
                 |                                  |
          /  (everything else)                   /api/...
          web app: static Vite build             API: FastAPI as a Vercel
          + security headers                     Function (Python)
                                                    |
                                     Neon Postgres (free plan, via the Vercel
                                     Marketplace), pooled connection

   GitHub Actions: migrate the database, then deploy; the daily clean-up job
```

**Why one project and one address.** Sign-in keeps its refresh token in a
`SameSite=Strict` cookie, which the browser only sends when the web app and
the API are the same site. `vercel.app` is on the public suffix list, so two
Vercel projects (`task-master-web.vercel.app` and
`task-master-api.vercel.app`) count as two different sites and sign-in would
break. Serving both from one project on one address, with the API under
`/api`, makes every API call same-origin: the cookie works, no CORS is
involved, and later a custom domain just replaces the address.

**Why this works on Vercel now.** Vercel runs the API as short-lived
serverless copies. Since PR #9 the rate limits and the login throttle live in
Postgres and the one-process lock is gone, so any number of copies share them
correctly.

**Cost: nothing to start.** Vercel Hobby and Neon Free are free, with limits:

- **Vercel Hobby is for personal, non-commercial use only**, and pauses a
  project that reaches its monthly limits (no overage billing). Before
  charging anyone (premium features), move to Pro ($20/month plus usage).
- **Neon Free:** about 0.5–1 GB storage and 100 compute hours per project a
  month (sources differ). The database sleeps when idle and takes a moment
  to wake. Backups are limited, so step 10 adds our own.
- **Cold starts:** the first API request after a quiet spell takes a second
  or two longer while Vercel starts the function.
- **The address:** `task-master.vercel.app` is shared Vercel space. It works
  fine, but it looks less trustworthy than your own domain for a public
  launch (Part F).

## Part A: prepare the code **(code)**

Do these on a branch (for example `deploy/vercel` from `master`), with tests,
then merge before Part B.

### A1. One Vercel project for web and API

Vercel's "Services" let one project hold a frontend and a backend, routed by
path. Vercel's official **Vite + FastAPI starter** template uses exactly
this; copy its root `vercel.json` and adapt it rather than writing one from
memory:

- frontend service: root `web`, framework Vite, built with the npm workspace
  (it needs `packages/api-client` from the repo root);
- backend service: root `backend`, FastAPI, entrypoint `app:app` (A2);
- a rewrite sending `/api/(.*)` to the backend service; everything else goes
  to the frontend.

Check one detail on the first deploy: whether the backend receives paths
**with** the `/api` prefix (`/api/goals`) or **without** it (`/goals`). A3
handles both, but must be set to match.

If Services are not available on Hobby when you try, the fallback is two
projects where the web project's `vercel.json` rewrites `/api/:path*` to the
API project's address (a proxy). That keeps one address for the browser, but
check the API still sees real visitor addresses, not Vercel's proxy (step 11,
point 6).

### A2. A Vercel entrypoint for the API

Vercel finds a FastAPI app named `app` in `app.py`, `index.py`, `main.py` and
similar names. Our app is built by a factory, so add `backend/app.py`:

```python
"""Vercel entrypoint: the API app, built from environment settings."""

from task_master.main import create_app

app = create_app()
```

If Vercel does not pick it up, name it in `backend/pyproject.toml`:

```toml
[tool.vercel]
entrypoint = "app:app"
```

Python: the project uses 3.14, which Vercel lists as supported. Vercel reads
`pyproject.toml` and `uv.lock`; if a build fails on dependencies, export a
`requirements.txt` with `uv export --no-dev --no-hashes > requirements.txt`.

### A3. Serving the API under `/api`

Add a setting `TASK_MASTER_ROOT_PATH` (default empty):

- If the backend receives `/api/...` paths (prefix kept), set it to `/api`
  and have `create_app` mount the API under that prefix.
- If Vercel strips the prefix, leave the routes as they are.

Either way the **refresh cookie path** must match what the browser sees:
today it is `/auth/web`; behind `/api` it must be `/api/auth/web`, or the
browser never sends the cookie back and users are signed out on every
reload. Make the cookie path `{public prefix}/auth/web`, with the public
prefix as a setting (for example `TASK_MASTER_PUBLIC_PREFIX=/api`), and test
it.

### A4. Web app calls the API on the same address

Build the web app with `VITE_API_URL=/api` (a relative address), so every
call goes to `https://<your address>/api/...`. Check that `web/src/api.ts`
and the generated client accept a relative base URL, and test it.

### A5. Database connections fit for serverless

Each function copy would otherwise keep its own pool of connections. Use
Neon's **pooled** connection (PgBouncer in transaction mode) and stop asyncpg
from caching prepared statements, which PgBouncer cannot share. Add a setting
such as `TASK_MASTER_DATABASE_POOLED: bool = False`; when true, create the
engine with:

```python
create_async_engine(
    url,
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
)
```

Neon's connection strings end in `?sslmode=require&channel_binding=require`,
which asyncpg does not accept. Our URL must use the asyncpg driver and
`ssl=require` instead:

```
postgresql+asyncpg://USER:PASSWORD@HOST-pooler.REGION.aws.neon.tech/DB?ssl=require
```

The same host without `-pooler` is the **direct** connection, used for
migrations and the clean-up job.

### A6. `/health` checks the database

Make `/health` run `SELECT 1` and answer 503 if the database is unreachable,
so an uptime check reports a broken database, not just a running function.

### A7. The real client address

Vercel puts the visitor's address in `x-forwarded-for` and overwrites any
value the visitor sent, so on Vercel the header can be trusted. Set
`TASK_MASTER_TRUSTED_PROXIES=["*"]` in production so rate limits and the
login throttle see real addresses. Only do this on Vercel: anywhere the API
can be reached directly, `*` would let clients fake their address.

### A8. Security headers for the web app

In the root `vercel.json`, add the headers from `docs/security.md` for the
web app's pages. Because the API is on the same address, `connect-src` is
simply `'self'`:

```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" },
        { "key": "Strict-Transport-Security", "value": "max-age=31536000; includeSubDomains" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" }
      ]
    }
  ]
}
```

The API sets its own, stricter headers on `/api` responses.

### A9. Deploy workflow: migrate, then deploy

Vercel deploys on every push by itself, which could put new API code live
before the database is migrated. Instead:

1. In the root `vercel.json`, turn off Git deploys:
   `"git": { "deploymentEnabled": false }`.
2. Add `.github/workflows/deploy.yml`, run on pushes to `master` after CI
   passes: install uv, run `uv run alembic upgrade head` against the
   **direct** database URL, then deploy with the Vercel CLI
   (`vercel deploy --prod --token $VERCEL_TOKEN`).

### A10. The daily clean-up job

Add `.github/workflows/cleanup.yml` on a daily schedule (for example
`cron: "0 3 * * *"`), running `uv run python -m task_master.cleanup` with the
**direct** database URL. It deletes old finished tasks, read notifications
and ended rate-limit windows.

### A11. Tests and docs

Tests for the root path and cookie path, the pooled engine settings,
`/health`, and a relative API address in the web app; update `CLAUDE.md`,
`docs/security.md` and `backend/README.md`. Then merge.

## Part B: accounts and services

### 1. Create the Vercel account

Sign up at vercel.com with GitHub, on the Hobby plan, and allow access to the
`task-master` repository.

### 2. Create the database

Vercel → Storage (Marketplace) → Neon → Free plan. Pick the region closest to
your users and remember it: the API function should run in the same region.
Vercel adds `DATABASE_URL` (pooled) and `DATABASE_URL_UNPOOLED` (direct) to
the connected project. We do not use them as they are (see A5); copy them to
build our two URLs:

- **Pooled, for the API:** `postgresql+asyncpg://…-pooler…/DB?ssl=require`
- **Direct, for migrations and clean-up:** `postgresql+asyncpg://…(no -pooler)…/DB?ssl=require`

### 3. Generate the auth secret

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep it in a password manager. Never commit it.

## Part C: the project

### 4. Create the project

Vercel → Add New → Project → import `task-master`:

- **Project name:** `task-master` (this becomes `task-master.vercel.app`; if
  taken, Vercel adds a suffix, and that is your address)
- **Root Directory:** the repository root (the root `vercel.json` from A1
  points at `web` and `backend`)
- **Function region** (Settings → Functions): the same region as Neon.

Vercel Hobby protects **preview** deployments behind a Vercel sign-in by
default; the production address stays public. That is fine.

### 5. Environment variables (Production)

Replace `task-master.vercel.app` with your actual address.

| Name | Value |
| --- | --- |
| `TASK_MASTER_ENVIRONMENT` | `production` |
| `TASK_MASTER_DATABASE_URL` | the pooled URL from step 2 |
| `TASK_MASTER_DATABASE_POOLED` | `true` |
| `TASK_MASTER_AUTH_SECRET` | the secret from step 3 |
| `TASK_MASTER_CORS_ORIGINS` | `["https://task-master.vercel.app"]` |
| `TASK_MASTER_TRUSTED_PROXIES` | `["*"]` |
| `TASK_MASTER_ROOT_PATH` / `TASK_MASTER_PUBLIC_PREFIX` | as decided in A3 |
| `VITE_API_URL` | `/api` |

Production refuses to start without an HTTPS origin and a 32+ character
secret, so a typo shows up as a failed deploy, not a weak setup. (All calls
are same-origin, so CORS is not used, but production still requires the
origin to be set.)

## Part D: GitHub automation

### 6. Secrets for the workflows

GitHub → repository → Settings → Secrets and variables → Actions:

| Secret | Value |
| --- | --- |
| `DATABASE_URL_DIRECT` | the direct URL from step 2 |
| `VERCEL_TOKEN` | Vercel → Account Settings → Tokens → create |
| `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | from the project → Settings → General |

### 7. First deploy

Run the `deploy` workflow (or push to `master`): it migrates the empty Neon
database to the latest schema, then deploys web and API together.

### 8. Check which `/api` setting is right

Open `https://task-master.vercel.app/api/health`. If it answers
`{"status": "ok"}`, the prefix setting from A3 matches. If it answers 404,
switch the setting (prefix kept vs stripped) and redeploy.

### 9. Monitoring

- Add a free uptime check (for example UptimeRobot or Better Stack) on
  `https://task-master.vercel.app/api/health`, every 5 minutes, alerting by
  email.
- Vercel → the project → Logs shows API errors and our JSON security logs.

### 10. Backups

Neon Free keeps only a short restore window. Add a nightly workflow that runs
`pg_dump` against the direct URL and stores the file in a private bucket (for
example Cloudflare R2's free storage), keeping 30 days. Then test a restore
into a scratch database once, so you know it works.

## Part E: check it

### 11. Smoke test

1. `/api/health` answers `{"status": "ok"}`; `/api/docs` answers 404 (hidden
   in production).
2. Open the address, create an account, sign in, then **reload the page**:
   you stay signed in. This proves the refresh cookie and its path work.
3. Add a goal, a task and a routine; tick a step.
4. Enter a wrong password 5 times: the 5th is locked for a minute.
5. Browser dev tools → Network → the page's response headers include the
   Content-Security-Policy, and the console shows no CSP errors.
6. From another network (phone data), sign in normally while step 4's lock
   is still on: you are not locked out, which shows visitor addresses are
   seen correctly.
7. Run the `cleanup` workflow by hand once; it succeeds.

## Part F: later, your own domain

No code changes needed:

1. Buy the domain on Cloudflare Registrar (about $10–11 a year for a `.com`).
2. Vercel → project → Settings → Domains → add `tasks.yourdomain.com` (or the
   bare domain). Add the DNS record Vercel shows in Cloudflare → DNS, with
   the proxy **off** (grey cloud, "DNS only").
3. Change `TASK_MASTER_CORS_ORIGINS` to the new address and redeploy.
4. Point the uptime check at the new address.

The `vercel.app` address keeps working too, but each address has its own
cookie, so people signed in on one must sign in again on the other.

## Later

- An email provider (password reset, verification).
- Privacy policy and terms; data export.
- Serve the font ourselves instead of from Google Fonts.
- Move to Vercel Pro before any paid features.

## Sources

- [Vercel: Vite + FastAPI starter (Services)](https://vercel.com/templates/react/vite-fastapi-starter)
- [Vercel: Can I set a cookie from my project subdomain to vercel.app?](https://vercel.com/kb/guide/can-i-set-a-cookie-from-my-vercel-project-subdomain-to-vercel-app)
- [Vercel: Understanding the SameSite cookie attribute](https://vercel.com/blog/understanding-the-samesite-cookie-attribute)
- [web.dev: SameSite cookies explained](https://web.dev/articles/samesite-cookies-explained)
- [Vercel: Rewrites](https://vercel.com/docs/routing/rewrites)
- [Vercel: Deploy a FastAPI app](https://vercel.com/docs/frameworks/backend/fastapi)
- [Vercel: Python runtime](https://vercel.com/docs/functions/runtimes/python)
- [Vercel: Backends on Vercel](https://vercel.com/docs/frameworks/backend)
- [Vercel: What is FastAPI (supported Python versions)](https://vercel.com/i/what-is-fastapi)
- [How to deploy a uv project to Vercel (pydevtools)](https://pydevtools.com/handbook/how-to/how-to-deploy-a-uv-project-to-vercel/)
- [Vercel Community: monorepo API route serves HTML instead of JSON](https://community.vercel.com/t/monorepo-api-route-fails-on-vercel-serves-html-instead-of-json/22519)
- [Vercel: Request headers](https://vercel.com/docs/headers/request-headers)
- [Neon: Vercel native integration](https://neon.tech/docs/guides/vercel-native-integration)
- [Vercel Marketplace: Neon](https://vercel.com/marketplace/neon)
- [SQLAlchemy discussion: asyncpg statement cache with PgBouncer](https://github.com/sqlalchemy/sqlalchemy/discussions/10246)
- [The asyncpg + PgBouncer prepared statement trap (goldlapel)](https://goldlapel.com/grounds/connection-pooling/asyncpg-pgbouncer-prepared-statement-trap)
- [Neon: Free plan limits](https://neon.com/faqs/free-plan-limits-and-quotas)
- [Vercel pricing breakdown 2026 (flexprice.io)](https://flexprice.io/blog/vercel-pricing-breakdown)
- [Cloudflare Registrar pricing (frontdeskreview.com)](https://frontdeskreview.com/software/domain-registrars/cloudflare-registrar/)
