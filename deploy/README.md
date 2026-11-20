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
