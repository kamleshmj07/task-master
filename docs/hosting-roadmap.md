# Hosting roadmap

Research for taking Task Master to production, gathered on 2026-11-25. Nothing
here is decided yet. Prices come mostly from third-party 2026 pricing
write-ups that disagree in places: treat them as estimates and confirm on each
provider's own pricing page before buying.

## Where we stand

The app itself is production-ready; the infrastructure around it is not built.

**Already in the code**

- Production mode refuses to start without HTTPS CORS origins and a strong
  secret, and hides `/docs`.
- Security headers (HSTS in production), rate limits, login throttling,
  password re-check pauses.
- JSON security logs without personal data.
- `TASK_MASTER_TRUSTED_PROXIES` for the real client IP behind a proxy.
- Alembic migrations, tested in CI (upgrade, downgrade, model parity).
- CI: lint, types, tests (85% coverage floor), dependency audits, API
  contract check.
- `/health` endpoint and the clean-up job (`python -m task_master.cleanup`).

**Missing before launch**

| Area | Gap |
| --- | --- |
| Hosting | No host chosen. Everything below depends on it. |
| Build and run | No Dockerfile; no production build or server for the web app. `docker-compose.yml` only runs the dev database. |
| Domain and HTTPS | No domain. The web app and API must share one site (for example `tasks.` and `api.` subdomains of one domain) or the sign-in cookie is not sent. |
| Web security headers | The CSP and other headers in `docs/security.md` must be set wherever the web app is served. |
| Deploys | No deploy step in CI. Migrations must run on each release. |
| Secrets | Production secrets and the database URL must live in the host's secret store. |
| Scheduled job | The clean-up job is not scheduled anywhere. |
| Backups | No database backups; no tested restore. |
| Monitoring | No uptime check, error tracking, or log collection. |
| Email | No provider: no password reset or email verification, and sign-up still reveals whether an email is taken. |
| Code gaps | `/health` does not check the database. (The single-process lock is fixed, see below.) |
| Launch basics | Privacy policy and terms; a way for users to export their data. |
| Optional | The font loads from Google Fonts; serving it ourselves would avoid sending users to a third party. |

## The single-process problem, and the fix

Rate-limit and login-throttle counters live in memory, so production holds a
Postgres advisory lock and a second API process refuses to start
(`single_process.py`). Hosts with zero-downtime deploys start the new version
before stopping the old one, so the new one refuses to start and the deploy
fails.

**Fix (done 2026-11-25, branch `feature/shared-rate-limits`):** in
production the counters now live in Postgres, shared by every API process,
and the lock is gone. That lifts the one-process limit everywhere, works on
every host below, and closes the parked security finding about it. Where the
tables below say "needs the fix", that is now done.

## Top 5 paid options

What Task Master needs: one API process, Postgres with backups, a static web
app with custom security headers, a daily clean-up job, automatic HTTPS.

| Option | Est. cost per month | Database backups | Scheduled clean-up | Works with "one API process" as is? | Upkeep |
| --- | --- | --- | --- | --- | --- |
| **1. Render** | ~$13–15: $7 API, $6 Postgres, about $1 cron; static web app free | Managed; check retention on your plan | Built-in cron jobs | No: zero-downtime deploys overlap old and new, so needs the fix above | Low |
| **2. Fly.io** | ~$5 API + Managed Postgres ~$38 (a $4 dev tier was announced but not confirmed) | Managed | Scheduled machines | Yes, with the `immediate` deploy strategy (old stopped first; a few seconds of downtime) | Low to medium |
| **3. Railway** | ~$5–15 on Hobby ($5 includes $5 of usage) | Built-in backups may be Pro only; their docs suggest a cron job copying the database to off-site storage | Built-in cron | Probably needs the fix | Low |
| **4. DigitalOcean** (App Platform + Managed Postgres) | ~$20–27: $5–12 API, ~$15 Postgres; static web app free | Managed | Scheduled jobs | Rolling deploys overlap, so needs the fix | Low |
| **5. Hetzner VPS** with Docker Compose and Caddy | ~€4.50–8.50 for one small server (prices rose in 2026) | Ours to set up: nightly copy to off-site storage, plus server snapshots | Cron on the server | Yes: a restart stops the old version first | High: OS updates, security, monitoring, restore tests |

**Recommendation for paid:** Render plus the Postgres-counters fix. Cheap for
a few users, managed database with backups, built-in cron, free static
hosting with custom headers, least upkeep. Fly.io works without the code
change but its managed Postgres costs more. Hetzner is cheapest if running a
server yourself is acceptable.

## Free options

Free hosting is possible, with trade-offs.

| Piece | Free option | Catch |
| --- | --- | --- |
| Web app | Cloudflare Pages (static, security headers via a `_headers` file) | None that matters here |
| API | Render free web service (one instance; 750 hours a month covers a single service) | Sleeps after 15 minutes without traffic; the next visit waits about a minute |
| Database | Neon free Postgres (1 GB per project; scales to zero when idle) | Short pause on wake-up; limited restore options |
| Clean-up job | Scheduled GitHub Actions workflow | Runs the job remotely against the database |
| Backups | Nightly database copy to Cloudflare R2 free storage, from a scheduled job | We build and test it ourselves |
| Domain | About $10–11 a year: the only real cost | Needed, see below |

**Avoid:** Render free Postgres (expires after 30 days, no backups) and
Supabase free (pauses after a week of little activity).

**The other free route:** an Oracle Cloud "Always Free" server running
everything with Docker Compose and Caddy. A real always-on server, but Oracle
halved the free allowance in 2026, may reclaim servers it considers idle, and
needs a credit card. Not trustworthy enough for a public launch.

The API needs the Postgres-counters fix on the free route too.

## Vercel, Heroku and Netlify

Checked on 2026-11-25. The key fit question: the API is a long-running
FastAPI process that keeps rate-limit counters in memory and holds a
Postgres lock so only one process runs. Serverless platforms (Vercel,
Netlify) run many short-lived copies instead, which breaks both until the
counters move to Postgres; they also need a pooled database connection.

| Platform | Web app | API | Cost | Verdict |
| --- | --- | --- | --- | --- |
| **Vercel** | Excellent (static hosting, headers in `vercel.json`) | Runs FastAPI as serverless functions (Python 3.12–3.14), but only after the Postgres-counters change and removing the single-process lock; the clean-up job would become a protected endpoint called by Vercel Cron | Hobby free but personal, non-commercial only (paused at its limits); Pro $20/month + usage | Good for the web app; a poor fit for the API today |
| **Heroku** | Possible, but wasteful (needs a dyno) | Fits as is: one long-running dyno; deploys without preboot stop the old dyno first | No free tier. Basic dyno $7 + Postgres Essential-0 $5 ≈ $12/month (Eco $5 dynos sleep after 30 min) | Works, but no cheaper than Render, and reports describe Heroku as in "sustaining mode" (maintained, not growing) |
| **Netlify** | Excellent (free plan, headers in `_headers`) | No: functions are JavaScript/TypeScript and Go; first-class Python is not confirmed | Free plan: 300 credits a month, hard limit | Good for the web app only |

**Cloudways** (checked 2026-11-25) is managed hosting built mainly for
PHP and WordPress, on top of DigitalOcean, Vultr and other clouds, from about
$11–14 a month. Its newer Velocity plans ($20/month) run Node.js apps with
Postgres on the same server. No first-class Python, FastAPI or Docker
support was found, and no managed Postgres, so it does not suit the API.

**Conclusion:** none of the three beats the recommended setup. Vercel or
Netlify could replace Cloudflare Pages for the web app; the API is still best
on Render (or Heroku, at similar cost but with a less certain future).

## Domain

Yes: buy one domain and host most apps under it.

- **Cloudflare Registrar** sells at cost with no markup: about $10–11 a year
  for a `.com`, renewing at the same price, with privacy protection and
  DNSSEC included. The domain must use Cloudflare's DNS (free).
- The domain and the hosting are separate: buy the name once, then point a
  subdomain at whichever host runs each app. Every host above supports custom
  domains with automatic HTTPS.
- One domain, many apps: for example `tasks.yourname.com` (web) and
  `api.yourname.com` (API), plus other apps at `blog.`, `notes.` and so on.
  Two subdomains of one domain count as the same site, which is what Task
  Master's sign-in needs.
- Free platform addresses (`*.pages.dev`, `*.onrender.com`) count as separate
  sites, so sign-in would not work on them. This is why the domain is needed
  even on the free route.

## Suggested path

1. Buy the domain on Cloudflare Registrar (~$11 a year).
2. Make the Postgres-counters change, and have `/health` check the database.
3. Start on the free setup while users are the owner and a few friends.
4. Before a public launch, move the API and database to Render's paid plans
   (~$13–15 a month) for no wake-up delay and managed backups. The domain,
   the web app on Cloudflare Pages and the code change carry over unchanged.
5. Then: monitoring, email provider, privacy policy and terms, data export.

## Open questions to settle

- Free first, or straight to paid?
- Which host for the API and database?
- Domain name.
- Email provider (password reset, verification).
- Where monitoring and error tracking go.

## Sources

- [Render docs: Deploy for free](https://render.com/docs/free)
- [Render docs: How deploys work](https://docs.render.com/deploys)
- [Render docs: Persistent disks](https://docs.render.com/disks)
- [How Render handles zero-downtime deploys](https://render.com/articles/how-render-handles-zero-downtime-deploys)
- [Render: Platforms with a real free tier in 2026](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)
- [Render pricing 2026 (temps.sh)](https://temps.sh/blog/render-pricing-2026)
- [Render pricing 2026 (budgetforge.dev)](https://www.budgetforge.dev/tools/render-pricing-2026)
- [Render pricing on G2](https://www.g2.com/products/render-render/pricing)
- [Fly.io pricing 2026 (activepieces)](https://www.activepieces.com/blog/fly-io-pricing-in-2026-for-machines-volumes-and-ips)
- [Fly.io Managed Postgres pricing (hoststack.dev)](https://hoststack.dev/blog/fly-managed-postgres-pricing-2026)
- [Fly.io community: Managed Postgres for $4 a month](https://community.fly.io/t/highly-available-managed-postgres-for-4-a-month/29144)
- [Fly.io docs: Deploy](https://fly.io/docs/apps/deploy/)
- [Fly.io: Seamless deployments](https://fly.io/docs/blueprints/seamless-deployments/)
- [Railway pricing 2026 (DEV Community)](https://dev.to/nayankyada/railway-pricing-2026-free-tier-limits-usage-costs-when-to-upgrade-1acm)
- [Railway pricing 2026 (justinmckelvey.com)](https://justinmckelvey.com/blog/railway-pricing)
- [Railway docs: Back up and restore Postgres](https://docs.railway.com/guides/postgres-backups-restores)
- [DigitalOcean pricing 2026 (justinmckelvey.com)](https://justinmckelvey.com/blog/digitalocean-pricing)
- [DigitalOcean pricing 2026 (kuberns.com)](https://kuberns.com/blogs/digitalocean-pricing/)
- [DigitalOcean Managed PostgreSQL review (infratally.com)](https://infratally.com/articles/digitalocean-managed-postgres-deep-dive/)
- [Hetzner Cloud review 2026 (Better Stack)](https://betterstack.com/community/guides/web-servers/hetzner-cloud-review/)
- [Hetzner Cloud prices 2026 (cloudtally.eu)](https://cloudtally.eu/hetzner-cloud-prices)
- [Hetzner price increase 2026 (sota.io)](https://sota.io/blog/hetzner-price-increase-managed-eu-paas-alternative-2026)
- [Neon: Free plan limits and quotas](https://neon.com/faqs/free-plan-limits-and-quotas)
- [Neon plans](https://neon.tech/docs/introduction/plans)
- [Neon pricing](https://neon.com/pricing)
- [Supabase: Do projects pause when inactive?](https://supabase.com/kb/faqs/platform/free-project-pausing)
- [Supabase: Project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)
- [Oracle: Always Free resources](https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm)
- [InfoQ: Oracle Cloud free tier limits](https://infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)
- [Linux Today: Oracle cuts free tier Ampere A1 in half](https://www.linuxtoday.com/blog/oracle-quietly-cuts-free-tier-ampere-a1-resources-in-half/)
- [Vercel: Best Python hosting for FastAPI, Flask and Django](https://vercel.com/i/best-python-hosting)
- [Vercel pricing breakdown 2026 (flexprice.io)](https://flexprice.io/blog/vercel-pricing-breakdown)
- [Vercel pricing and Fluid compute (usagepricing.com)](https://www.usagepricing.com/blueprint/vercel)
- [Heroku pricing 2026 (activepieces)](https://www.activepieces.com/blog/heroku-pricing-2026-plans-costs-and-alternatives)
- [Heroku is getting expensive: 2026 cost calculator (DEV Community)](https://dev.to/nexgendata/heroku-is-getting-expensive-a-2026-cost-calculator-migration-guide-1579)
- [Heroku in sustaining mode (bex.co)](https://bex.co/blog/2026/10/17/heroku-sustaining-mode-vs-hetzner-box-cost)
- [Netlify pricing 2026 (kuberns.com)](https://kuberns.com/blogs/netlify-pricing/)
- [Netlify free plan limits (getvoroa.com)](https://getvoroa.com/blog/netlify-free-plan-limits/)
- [Netlify review 2026 (dupple.com)](https://dupple.com/reviews/netlify)
- [Cloudways review 2026 (devopscube.com)](https://devopscube.com/cloudways-review/)
- [Cloudways vs DigitalOcean (getdeploying.com)](https://getdeploying.com/cloudways-vs-digitalocean)
- [Cloudways Velocity vs Render (appstackbuilder.com)](https://appstackbuilder.com/compare/cloudways-velocity-vs-render)
- [Cloudflare plans](https://www.cloudflare.com/plans/)
- [Cloudflare Registrar pricing (frontdeskreview.com)](https://frontdeskreview.com/software/domain-registrars/cloudflare-registrar/)
- [Cloudflare Registrar review (startupowl.com)](https://startupowl.com/reviews/cloudflare-registrar)
