#!/usr/bin/env python3
"""
Import subscriptions from Personal.xlsx → Wallos SQLite DB.

Usage:
    python3 wallos-import.py           # dry run (default)
    python3 wallos-import.py --execute # actually insert
"""

import re
import sys
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import openpyxl

XLSX_PATH = Path.home() / "Downloads/Personal.xlsx"
DB_PATH = Path.home() / "wallos/db/wallos.db"
BACKUP_PATH = DB_PATH.with_suffix(".db.bak")

DRY_RUN = "--execute" not in sys.argv
USER_ID = 1

# Wallos cycle IDs: 1=Daily, 2=Weekly, 3=Monthly, 4=Yearly
CYCLE_YEARLY = 4
FREQUENCY = 1  # every 1 cycle

# Category mapping: excel → wallos name (will create if missing)
CATEGORY_MAP = {
    "Investing":      "Investing",
    "Miscellaneous":  "Miscellaneous",
    "News":           "News & Magazines",
    "Streaming":      "Entertainment",
    "Tech Newsletter": "News & Magazines",
    "Personal":       "Miscellaneous",
}


def parse_price(formula, country):
    """Return (price_float, currency_id).
    India formulas: extract INR amount → INR (id=24).
    US / simple formulas: evaluate arithmetic → USD (id=2).
    """
    if formula is None:
        return None, 2

    val = formula
    if isinstance(val, (int, float)):
        return float(val), (24 if country == "India" else 2)

    val = str(val).strip()

    # India GOOGLEFINANCE formula: extract INR amount
    m = re.search(r'"(\d+(?:\.\d+)?)\*GOOGLEFINANCE', val)
    if m:
        return float(m.group(1)), 24  # INR

    # Simple arithmetic formula like =8.25 * 12 or =65 * 12
    if val.startswith("="):
        expr = val[1:].strip()
        # Only allow digits, spaces, +, -, *, /, (, ), .
        if re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', expr):
            return float(eval(expr)), 2  # USD

    # Fallback: try float cast
    try:
        return float(val), 2
    except (ValueError, TypeError):
        return None, 2


def get_or_create_category(cur, name):
    cur.execute("SELECT id FROM categories WHERE name = ? AND user_id = ?", (name, USER_ID))
    row = cur.fetchone()
    if row:
        return row[0]
    return None  # new category — will be created via docker exec on --execute


def build_name(platform, service):
    if platform == "Independent":
        return service
    # Avoid "Netflix - Netflix Standard" type redundancy
    if service.lower().startswith(platform.lower()):
        return service
    return f"{platform} - {service}"


def main():
    wb = openpyxl.load_workbook(str(XLSX_PATH), data_only=False)
    ws = wb["Subscriptions"]

    rows = []
    for i, row in enumerate(ws.iter_rows(min_row=4, values_only=False), start=4):
        vals = [c.value for c in row]
        if not any(v is not None for v in vals[:9]):
            continue

        country   = vals[2]
        category  = vals[3]
        platform  = vals[4]
        service   = vals[5]
        status    = vals[6]
        exp_date  = vals[7]
        price_raw = row[8].value  # raw formula or value

        if status == "Wishlist":
            continue
        if not service:
            continue

        rows.append({
            "row": i,
            "country": country,
            "category": category,
            "platform": platform,
            "service": service,
            "status": status,
            "exp_date": exp_date,
            "price_raw": price_raw,
        })

    print(f"Found {len(rows)} subscriptions to import (Wishlist skipped)\n")

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cur = con.cursor()

    # Resolve / create categories
    cat_id_cache = {}
    new_categories = []
    for r in rows:
        wallos_cat = CATEGORY_MAP.get(r["category"], "Miscellaneous")
        if wallos_cat not in cat_id_cache:
            cat_id = get_or_create_category(cur, wallos_cat)
            cat_id_cache[wallos_cat] = cat_id
            if cat_id is None:
                new_categories.append(wallos_cat)

    inserts = []
    skipped = []

    for r in rows:
        price, currency_id = parse_price(r["price_raw"], r["country"])
        if price is None:
            skipped.append(r["service"])
            continue

        name = build_name(r["platform"], r["service"])
        wallos_cat = CATEGORY_MAP.get(r["category"], "Miscellaneous")
        cat_id = cat_id_cache[wallos_cat]

        next_payment = None
        if isinstance(r["exp_date"], datetime):
            next_payment = r["exp_date"].strftime("%Y-%m-%d")

        auto_renew = 0 if r["status"] == "Expiring" else 1
        inactive   = 0

        inserts.append({
            "name": name,
            "price": round(price, 2),
            "currency_id": currency_id,
            "cycle": CYCLE_YEARLY,
            "frequency": FREQUENCY,
            "next_payment": next_payment,
            "category_id": cat_id,
            "auto_renew": auto_renew,
            "inactive": inactive,
            "user_id": USER_ID,
            "notes": f"Platform: {r['platform']}" if r["platform"] != "Independent" else "",
            "payment_method_id": 2,  # Credit Card default
            "payer_user_id": USER_ID,
            "notify": 0,
            "notify_days_before": 0,
        })

    # Print preview
    currency_label = {2: "USD", 24: "INR"}
    print(f"{'#':<3} {'Name':<45} {'Price':>10} {'Curr':<5} {'Next Payment':<14} {'AutoRenew'}")
    print("-" * 95)
    for idx, r in enumerate(inserts, 1):
        curr = currency_label.get(r["currency_id"], str(r["currency_id"]))
        date = r["next_payment"] or "no date"
        ar   = "yes" if r["auto_renew"] else "no (expiring)"
        print(f"{idx:<3} {r['name']:<45} {r['price']:>10.2f} {curr:<5} {date:<14} {ar}")

    if skipped:
        print(f"\nSkipped (could not parse price): {skipped}")

    if new_categories:
        print(f"\nNew categories to be created: {new_categories}")

    print(f"\nTotal: {len(inserts)} subscriptions")

    if DRY_RUN:
        print("\n[DRY RUN] No changes written. Re-run with --execute to import.")
        con.close()
        return

    # Build SQL statements to pipe into the container via docker exec
    import subprocess

    sql_lines = ["BEGIN;"]

    # Create new categories
    for name in new_categories:
        escaped = name.replace("'", "''")
        sql_lines.append(
            f"INSERT INTO categories (name, user_id) VALUES ('{escaped}', {USER_ID});"
        )

    for r in inserts:
        def q(v):
            if v is None:
                return "NULL"
            if isinstance(v, str):
                return "'" + v.replace("'", "''") + "'"
            return str(v)

        # Re-resolve category_id (now that we're inserting categories too)
        cat_name = None
        for cn, cid in cat_id_cache.items():
            if cid == r["category_id"]:
                cat_name = cn
                break

        sql_lines.append(
            f"INSERT INTO subscriptions "
            f"(name, price, currency_id, cycle, frequency, next_payment, category_id, "
            f"auto_renew, inactive, user_id, notes, payment_method_id, payer_user_id, "
            f"notify, notify_days_before) "
            f"VALUES ("
            f"{q(r['name'])}, {r['price']}, {r['currency_id']}, {r['cycle']}, {r['frequency']}, "
            f"{q(r['next_payment'])}, "
            f"(SELECT id FROM categories WHERE name = {q(cat_name)} AND user_id = {USER_ID}), "
            f"{r['auto_renew']}, {r['inactive']}, {r['user_id']}, "
            f"{q(r['notes'])}, {q(r['payment_method_id'])}, {q(r['payer_user_id'])}, "
            f"{r['notify']}, {r['notify_days_before']});"
        )

    sql_lines.append("COMMIT;")
    sql_input = "\n".join(sql_lines)

    result = subprocess.run(
        ["docker", "exec", "-i", "wallos", "sqlite3", "/var/www/html/db/wallos.db"],
        input=sql_input,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"\nError:\n{result.stderr}")
        sys.exit(1)

    con.close()
    print(f"\nInserted {len(inserts)} subscriptions into Wallos. Done!")
    print("\n⚠  Reminder: fill in next billing dates for:")
    print("   - Optimum - 300 Mbps Internet")
    print("   - Youtube Premium")
    print("   - Google One x2")


if __name__ == "__main__":
    main()
