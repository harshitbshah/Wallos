# Wallos Setup Documentation

## Overview
Wallos is a self-hosted subscription tracker running in Docker.
- Local: `http://localhost:8282`
- Oracle Cloud (production): `http://mywallos.duckdns.org` (IP: `152.70.200.81`)

---

## Local Setup

### Docker
```
docker run -d \
  --name wallos \
  --restart unless-stopped \
  -p 8282:80 \
  -v /home/harshit-shah/wallos/db:/var/www/html/db \
  -v /home/harshit-shah/wallos/logos:/var/www/html/images/uploads/logos \
  bellamy/wallos:latest
```

Data lives at:
- DB: `/home/harshit-shah/wallos/db/wallos.db` (SQLite)
- Logos: `/home/harshit-shah/wallos/logos/`

---

## Subscription Import from Excel

Script: `/home/harshit-shah/wallos-import.py`
Source: `~/Downloads/Personal.xlsx` → Subscriptions sheet

### What it does
- Reads subscriptions from the Excel sheet (columns: Country, Category, Platform, Service, Status, Expiring On, Price)
- India subscriptions: extracts INR amount from `GOOGLEFINANCE` formula, stores in INR
- US subscriptions: evaluates arithmetic formulas (e.g. `=8.25*12`), stores in USD
- Maps Excel categories to Wallos categories (creates "Investing" and "Miscellaneous" if missing)
- Status "Expiring" → imported as active with `auto_renew=0`
- Status "Wishlist" → skipped
- Platform prefix stripped from name when platform is "Independent"
- Defaults: `payer_user_id=1`, `payment_method_id=2` (Credit Card), `cycle=4` (Yearly), `frequency=1`

### Usage
```bash
python3 wallos-import.py           # dry run
python3 wallos-import.py --execute # actually insert
```

### Notes
- Uses `docker exec wallos sqlite3` to write (DB owned by Docker UID 82, not writable directly)
- Backs up DB to `wallos.db.bak` before writing

---

## Logo Fetching

Script: `/home/harshit-shah/wallos-logos.py`

### What it does
- Maps each subscription to its domain
- Fetches logos from Google favicon API (`https://t2.gstatic.com/faviconV2?...&size=128`)
- Falls back to DuckDuckGo favicon API (`https://icons.duckduckgo.com/ip3/{domain}.ico`) for failures
- Copies logos into container via `docker cp`
- Updates `logo` field in DB via `docker exec sqlite3`
- Reuses same logo file for subscriptions sharing a domain (e.g. all Substack newsletters)

### Usage
```bash
python3 wallos-logos.py           # dry run
python3 wallos-logos.py --execute # fetch and assign
```

### Notes
- Clearbit logo API is defunct (acquired by HubSpot)
- 7 independent newsletters have no domain and are skipped
- Folio Trail has no accessible favicon

---

## Manual Fixes Applied After Import

### Subscription name cleanup
```sql
-- Remove "Substack - " prefix (logo makes it redundant)
UPDATE subscriptions SET name = SUBSTR(name, 12) WHERE name LIKE 'Substack - %' AND user_id=1;

-- Remove "Savvy Trader - " prefix
UPDATE subscriptions SET name = SUBSTR(name, 16) WHERE name LIKE 'Savvy Trader - %' AND user_id=1;

-- Fix any remaining leading spaces or "- " artifacts
UPDATE subscriptions SET name = TRIM(name) WHERE user_id=1;
UPDATE subscriptions SET name = SUBSTR(name, 3) WHERE name LIKE '- %' AND user_id=1;
```

### Fix NULL fields (caused PHP warnings)
```sql
-- payer_user_id must not be NULL (stats_calculations.php arrays keyed by payer ID)
UPDATE subscriptions SET payer_user_id = 1 WHERE payer_user_id IS NULL AND user_id=1;

-- payment_method_id must not be NULL (defaulted to Credit Card = 2)
UPDATE subscriptions SET payment_method_id = 2 WHERE payment_method_id IS NULL AND user_id=1;
```

### Billing date fixes
```sql
-- Google One x2
UPDATE subscriptions SET next_payment = '2026-05-16' WHERE name = 'Google One x2' AND user_id=1;

-- Optimum (monthly $89.66, billing period 03/08/26 - 04/07/26)
UPDATE subscriptions SET price = 89.66, cycle = 3, frequency = 1, next_payment = '2026-04-08'
WHERE name = 'Optimum - 300 Mbps Internet' AND user_id=1;

-- YouTube Premium (family plan $26.16/3 = $8.72/month share, paid by family)
UPDATE subscriptions SET price = 8.72, cycle = 3, frequency = 1, next_payment = '2026-04-01'
WHERE name = 'Youtube Premium' AND user_id=1;
```

### INR exchange rate
Wallos exchange rates (used by `getPriceConverted()`) default to 1 for all currencies.
INR rate must be set manually or via Fixer API.

```sql
-- Manual update (approximate rate as of Mar 2026)
UPDATE currencies SET rate = 94.1543065 WHERE code = 'INR' AND user_id=1;
```

Fixer free tier (100 calls/month) is configured in Wallos Settings → Fixer API.
Wallos runs the exchange rate update cron daily at 2 AM (`0 2 * * *`).
Fixer free tier uses EUR as base; Wallos normalizes to main currency (USD) in code.

---

## Currency Setup
- Main currency: USD (id=2, rate=1)
- INR subscriptions stored natively in INR (id=24)
- Fixer API key set in Wallos Settings for daily auto-update

---

## Notifications
- Channel: Telegram
- Bot token: configured in Wallos Settings → Notifications → Telegram
- Chat ID: `5031925689` (Harshit's personal chat with the bot)
- Test: use the Test button in Wallos Settings → Notifications → Telegram
- Runs daily at 9 AM (inside container) — only fires if laptop/server is running

---

## AI Recommendations
- Provider: Gemini (`gemini-2.0-flash`)
- API key stored in DB (migrated with wallos.db)
- Runs weekly (Monday 1:30 AM) and/or monthly (1st, 4 AM) via cron
- Analyzes active subscriptions and returns 3–7 cost-saving suggestions
- Configured in Wallos Settings → AI Recommendations

---

## Fork & Overrides

Wallos runs upstream's Docker image (`bellamy/wallos:latest`) with personal customizations mounted on top as volume overrides. No custom image build needed.

### Changed files (vs upstream `ellite/Wallos`)
| File | What changed |
|------|-------------|
| `includes/i18n/en.php` | "Cancel reminder" label (was "Cancel by") |
| `index.php` | Clickable dashboard cards |
| `scripts/dashboard.js` | Quick-edit modal + cache buster |
| `settings.php` | Modal changes |
| `styles/styles.css` | Mobile nav modal fix |
| `subscriptions.php` | Modal changes |

These files live in `~/wallos/overrides/` on OCI, mounted into the container. **Never edit files inside the container directly** (via `docker exec` or `docker cp`) — changes won't survive a container restart.

### Deploying a change
```bash
# 1. Edit the file locally in ~/Projects/Wallos/
# 2. SCP to OCI (match the path under overrides/)
scp -i ~/.ssh/oracle_wallos <file> ubuntu@152.70.200.81:~/wallos/overrides/<path>

# PHP files are live immediately. JS/CSS need a hard refresh (Cmd+Shift+R).
```

### If container is ever recreated
```bash
ssh -i ~/.ssh/oracle_wallos ubuntu@152.70.200.81 "bash ~/wallos/deploy.sh"
```
`deploy.sh` remounts all overrides automatically — nothing is lost.

### Pulling upstream updates
```bash
cd ~/Projects/Wallos
git fetch upstream
git merge upstream/main
# Resolve conflicts in the 6 override files if needed
# Then scp updated files to OCI
```

---

## Oracle Cloud Deployment (Free Tier)

### VM Specs
- Shape: `VM.Standard.A1.Flex` (ARM, Always Free)
- OCPUs: 2, RAM: 12GB
- Image: Ubuntu 24.04 (aarch64)
- Region: us-ashburn-1
- Public IP: `152.70.200.81`
- Instance OCID: `ocid1.instance.oc1.iad.anuwcljtblgejoichxace7dho6zk36mshlbszmtpnudb2wxnbxcu4pyax4ma`

### Domain
- **DuckDNS**: `mywallos.duckdns.org` → `152.70.200.81`
- Access: `https://mywallos.duckdns.org` (HTTPS via Caddy + Let's Encrypt)
- Managed at: duckdns.org (sign in with Google)

### SSH Access
```bash
ssh -i ~/.ssh/oracle_wallos ubuntu@152.70.200.81
```
Key: `~/.ssh/oracle_wallos` (ed25519)

### OCI CLI
Installed at: `~/lib/oracle-cli/bin/oci`
Config: `~/.oci/config`
```bash
export PATH="$HOME/lib/oracle-cli/bin:$PATH"
```

### Firewall
Two layers must both allow traffic:

1. **Oracle Security List** (VCN-level) — managed via OCI CLI or console
   - Port 22 (SSH): open
   - Port 80 (HTTP / ACME challenge): open
   - Port 443 (HTTPS): open

2. **Ubuntu iptables** (host-level) — rules must appear BEFORE the REJECT rule
```bash
sudo iptables -I INPUT 5 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 5 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

### Caddy (HTTPS reverse proxy)
Installed via apt. Config at `/etc/caddy/Caddyfile`:
```
mywallos.duckdns.org {
    reverse_proxy localhost:8080
}
```
Caddy owns ports 80 and 443, auto-fetches and renews Let's Encrypt cert.
```bash
sudo systemctl enable caddy
sudo systemctl restart caddy
```

### Data Migration
```bash
# Copy DB and logos from local to Oracle VM
scp -i ~/.ssh/oracle_wallos /home/harshit-shah/wallos/db/wallos.db ubuntu@152.70.200.81:~/wallos/db/
scp -i ~/.ssh/oracle_wallos -r /home/harshit-shah/wallos/logos/. ubuntu@152.70.200.81:~/wallos/logos/
```

### Docker on Oracle VM
Wallos runs on port 8080 (Caddy proxies 443 → 8080):
```bash
docker run -d \
  --name wallos \
  --restart unless-stopped \
  -p 8080:80 \
  -v /home/ubuntu/wallos/db:/var/www/html/db \
  -v /home/ubuntu/wallos/logos:/var/www/html/images/uploads/logos \
  bellamy/wallos:latest
```

### Future Re-migration
To sync local changes to Oracle VM:
```bash
# Stop container, copy DB, restart
ssh -i ~/.ssh/oracle_wallos ubuntu@152.70.200.81 "docker stop wallos"
scp -i ~/.ssh/oracle_wallos /home/harshit-shah/wallos/db/wallos.db ubuntu@152.70.200.81:~/wallos/db/
ssh -i ~/.ssh/oracle_wallos ubuntu@152.70.200.81 "docker start wallos"
```

---

## PWA (Progressive Web App)

### How to install on Android
1. Open Chrome and go to `https://mywallos.duckdns.org`
2. Tap the three-dot menu → **"Add to Home Screen"** or **"Install app"**
3. App opens in standalone mode (no address bar) — true PWA install

### Why HTTPS is required
Chrome only registers service workers over HTTPS. Without it:
- No service worker = no PWA install prompt
- "Add to Home Screen" still appears but creates a plain browser shortcut (with address bar)
- HTTPS is handled by Caddy with auto-renewed Let's Encrypt cert

### Offline behavior
The service worker (`service-worker.js`) aggressively caches pages, assets, and logos.
When the server is down (e.g. Caddy stopped):
- **Cached UI loads fine** — looks like it's working
- **Any server action fails** — login, adding subscriptions, loading live data
- This is intentional PWA offline behavior, not a bug

### What's not yet implemented
- **Web Push notifications** — would replace Telegram/Discord hooks with native phone notifications
- Requires: VAPID keys, `/api/push/subscribe.php`, service worker push handler
- HTTPS (already done) is the only prerequisite

---

## Wallos Internals Reference

### Cron Schedule (inside container)
| Time | Job |
|------|-----|
| 1 AM daily | Update next payment dates |
| 2 AM daily | Update exchange rates (Fixer) |
| 8 AM daily | Send cancellation notifications |
| 9 AM daily | Send renewal notifications |
| Mon 1:30 AM | Generate AI recommendations (weekly) |
| 1st 4 AM | Generate AI recommendations (monthly) |

### Key DB Tables
- `subscriptions` — all subscriptions
- `currencies` — currency list with exchange rates
- `categories` — subscription categories
- `payment_methods` — payment method list
- `household` — household members (payer tracking)
- `ai_settings` / `ai_recommendations` — AI config and results
- `fixer` — Fixer API key and provider

### cycle IDs
| ID | Meaning |
|----|---------|
| 1 | Daily |
| 2 | Weekly |
| 3 | Monthly |
| 4 | Yearly |

### Notification Channels Supported
Email, Telegram, Discord, Ntfy, Gotify, Pushover, Webhook, Mattermost, Server Chan
