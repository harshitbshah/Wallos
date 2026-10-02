#!/usr/bin/env python3
"""
Fetch and assign logos to Wallos subscriptions.
Uses Google's favicon API → saves to Docker container → updates DB.

Usage:
    python3 wallos-logos.py           # dry run
    python3 wallos-logos.py --execute
"""

import os
import re
import sys
import time
import subprocess
import tempfile
import urllib.request

DB_PATH = "/var/www/html/db/wallos.db"
LOGO_DIR = "/var/www/html/images/uploads/logos"
USER_ID = 1
DRY_RUN = "--execute" not in sys.argv

# subscription name → domain (None = skip)
DOMAIN_MAP = {
    "Hasfit":                                           "hasfit.com",
    "Netflix - Standard":                               "netflix.com",
    "Claude Pro":                                       "anthropic.com",
    "The Ken":                                          "the-ken.com",
    "Monarch Money":                                    "monarchmoney.com",
    "Smallcase - H2 Wealth Builders Model":             "smallcase.com",
    "Robinhood Gold":                                   "robinhood.com",
    "Substack - Make Money, Make Time":                 "substack.com",
    "VIA Newsletter":                                   None,
    "Substack - Potential Multibaggers":                "substack.com",
    "Substack - Daniel Romero":                         "substack.com",
    "Substack - Global Equity Briefing":                "substack.com",
    "Substack - GabGrowth":                             "substack.com",
    "Substack - Beachman's Salty Trades":               "substack.com",
    "X Premium Basic Subscription":                     "x.com",
    "Substack - M.V. Cunha":                            "substack.com",
    "SOIC Research":                                    "soicfinance.in",
    "ZN Microcap Stock Advisory":                       None,
    "Savvy Trader - Shay's Growth Portfolio":           "savvytrader.com",
    "Savvy Trader - Shay's 4th Industrial Revolution Portfolio": "savvytrader.com",
    "Substack - Exponential View":                      "exponentialview.co",
    "Substack - SixSigmaCapital":                       "substack.com",
    "SOIC Global Research":                             "soicfinance.in",
    "Amazon Prime":                                     "amazon.com",
    "Sahil Bhadviya":                                   None,
    "Folio Trail":                                      "foliotrail.com",
    "Savvy Trader - Eggs In One Basket":                "savvytrader.com",
    "Blinkist":                                         "blinkist.com",
    "Substack - Outperforming the Market":              "substack.com",
    "Substack - The Pragmatic Optimist":                "substack.com",
    "Congruence Advisers":                              None,
    "Zen Nivesh Investing Club":                        None,
    "SOIC Membership":                                  "soicfinance.in",
    "Intrinsic Recommendation Service":                 None,
    "The Wrap":                                         None,
    "Keeper":                                           "keepersecurity.com",
    "Optimum - 300 Mbps Internet":                      "optimum.net",
    "Youtube Premium":                                  "youtube.com",
    "Google One x2":                                    "google.com",
}

def sanitize(name):
    name = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    name = name.replace(" ", "-")
    return name

def fetch_logo(domain):
    url = f"https://t2.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://{domain}&size=128"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            # Verify it's a valid image (PNG magic bytes or JPEG)
            if data[:4] in (b'\x89PNG', b'\xff\xd8\xff') or data[:4] == b'GIF8':
                return data
    except Exception as e:
        print(f"  Failed to fetch {domain}: {e}")
    return None

def docker_exec_sql(sql):
    result = subprocess.run(
        ["docker", "exec", "-i", "wallos", "sqlite3", DB_PATH],
        input=sql, capture_output=True, text=True
    )
    return result.returncode == 0, result.stderr.strip()

def main():
    # Get current subscriptions from DB
    result = subprocess.run(
        ["docker", "exec", "wallos", "sqlite3", DB_PATH,
         f"SELECT id, name, logo FROM subscriptions WHERE user_id={USER_ID};"],
        capture_output=True, text=True
    )
    subs = {}
    for line in result.stdout.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) >= 2:
            sub_id, name = parts[0], parts[1]
            existing_logo = parts[2] if len(parts) > 2 else ""
            subs[name] = {"id": sub_id, "logo": existing_logo}

    print(f"{'Action':<10} {'Name':<50} {'Domain'}")
    print("-" * 90)

    actions = []
    for name, domain in DOMAIN_MAP.items():
        sub = subs.get(name)
        if not sub:
            print(f"{'NOT FOUND':<10} {name:<50}")
            continue
        if not domain:
            print(f"{'SKIP':<10} {name:<50} no domain")
            continue
        if sub["logo"]:
            print(f"{'HAS LOGO':<10} {name:<50} {domain}")
            continue
        print(f"{'FETCH':<10} {name:<50} {domain}")
        actions.append({"name": name, "id": sub["id"], "domain": domain})

    print(f"\n{len(actions)} logos to fetch, {sum(1 for d in DOMAIN_MAP.values() if d is None)} skipped (no domain)")

    if DRY_RUN:
        print("\n[DRY RUN] Re-run with --execute to fetch and assign logos.")
        return

    print()
    seen_domains = {}  # domain → filename (reuse same logo for duplicates like substack)
    sql_updates = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for action in actions:
            name, sub_id, domain = action["name"], action["id"], action["domain"]

            if domain in seen_domains:
                filename = seen_domains[domain]
                print(f"  Reusing {filename} for {name}")
            else:
                print(f"  Fetching {domain} ...", end=" ", flush=True)
                data = fetch_logo(domain)
                if not data:
                    print("FAILED")
                    continue
                timestamp = int(time.time())
                filename = f"{timestamp}-{sanitize(domain)}.png"
                local_path = os.path.join(tmpdir, filename)
                with open(local_path, "wb") as f:
                    f.write(data)
                # Copy into container
                cp = subprocess.run(
                    ["docker", "cp", local_path, f"wallos:{LOGO_DIR}/{filename}"],
                    capture_output=True
                )
                if cp.returncode != 0:
                    print(f"COPY FAILED: {cp.stderr.decode()}")
                    continue
                seen_domains[domain] = filename
                print(f"OK ({len(data)//1024}KB → {filename})")
                time.sleep(0.3)  # be polite to the API

            escaped = filename.replace("'", "''")
            sql_updates.append(f"UPDATE subscriptions SET logo='{escaped}' WHERE id={sub_id} AND user_id={USER_ID};")

    if sql_updates:
        ok, err = docker_exec_sql("BEGIN;\n" + "\n".join(sql_updates) + "\nCOMMIT;")
        if ok:
            print(f"\nUpdated {len(sql_updates)} subscription logos. Done!")
        else:
            print(f"\nDB update failed: {err}")

if __name__ == "__main__":
    main()
