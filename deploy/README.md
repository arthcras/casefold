# Casefold live on the Hetzner server (Coolify)

Route of an update: change here → commit on `crypto-intelligence` → checks (workflows `tests`, `deploy-check`) →
on Arthur's word "zet live" the commit goes to the branch `live` → Coolify sees the push and deploys.

## What runs

| Service | Image | Reachable |
|---|---|---|
| `web` | `deploy/web/Dockerfile` (nginx): website at `/`, app at `/crypto.html`, data, Relate | casefoldcrypto.com; app.casefoldcrypto.com opens the app at `/` |
| `crawler` | `deploy/crawler/Dockerfile` (FastAPI) | only through `web` at `/api/crawler/` |

Left out of the public image on purpose: the back office (`workspace.html`), the platform console and other internal pages.
Neo4j (casefold-community) is a later step.

## One-time setup in Coolify (Arthur)

1. Coolify → Projects → New resource → **Public/Private Repository (GitHub App)** → `arthcras/casefold`.
2. Branch: **`live`**. Build pack: **Docker Compose**. Compose file: **`deploy/coolify/docker-compose.yml`**.
3. Service `web` → Domains: `https://casefoldcrypto.com,https://app.casefoldcrypto.com`.
   DNS in Cloudflare (casefoldcrypto.com): A records `@`, `app` and later `office` → the server's IP, proxy off (grey) until
   Coolify has its certificates; then proxy on and SSL/TLS mode Full (strict).
4. Environment variables (Coolify, not git):
   - `CRAWLER_TOKEN`: a long random string (for example from a password manager).
   - optional `TRONGRID_API_KEY`.
5. Turn on **Automatic deployment** (webhook on push), then Deploy.

Check after deploy: `/` shows the website, `/crypto.html` the app, `/api/crawler/health` answers `{"ok": true, ...}`.

## Updating

Claude makes the change, it is checked by the workflows, and goes to `live` only after "zet live" in the chat.
Back: Coolify keeps earlier deployments (Deployments → Redeploy an earlier one), or `live` is set back one commit.

## Back office: office.casefoldcrypto.com (behind Cloudflare Access)

The service `office` serves the workspace, the app with "Trace this wallet now", and the crawler with the server's
token. nginx lets a request through only when the crawler confirms the Cloudflare Access token (`/access/verify`);
without `CF_ACCESS_TEAM` and `CF_ACCESS_AUD` everything there is refused (401).

1. Cloudflare → DNS (casefoldcrypto.com): A `office` → server IP, **proxied (orange)**: Access works only through Cloudflare.
2. Cloudflare → Zero Trust → Access → Applications → Add → Self-hosted: domain `office.casefoldcrypto.com`,
   policy Allow → the e-mail addresses that may enter. Copy the **Application Audience (AUD) tag** and the team domain
   (`<team>.cloudflareaccess.com`, under Settings → Custom pages / Team domain).
3. Coolify → Environment Variables: `CF_ACCESS_TEAM` = the team domain, `CF_ACCESS_AUD` = the AUD tag.
4. Coolify → Domains: service `office` → `https://office.casefoldcrypto.com`, port 80. Deploy.

## Investigations on the server

In the back office (office.casefoldcrypto.com) the investigations are stored on the server, not only in the browser:
`casefold/crawler/cases.py`, in the crawler's SQLite file (`/data/crawler.sqlite`, Docker volume `crawler-data`).

- Who: taken from the Cloudflare Access token (e-mail); the server token alone is not enough.
- Versions: a save names the version it started from; a save from an older version is refused, and the app then shows
  the newer version and says who changed it.
- Audit trail: every create, change and delete is an event (who, when, version, SHA-256 of the document), chained by hash;
  the database refuses changes to it. Delete hides an investigation; the document and its history are kept.
- The browser keeps a copy and saves with the next change when the server was not reachable. Investigations made
  earlier in a browser move to the server the first time the back office is opened there.
- The public site and app (casefoldcrypto.com, app.casefoldcrypto.com) cannot reach them (`/api/crawler/cases` → 404);
  the public app keeps its investigations in the browser.
- Backup: the volume `crawler-data` holds everything; back it up (Coolify → the resource → Backups, or a copy of
  `/data/crawler.sqlite`) before relying on it for client work.
