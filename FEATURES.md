# Wallos Feature Ideas

Fork: https://github.com/harshitbshah/Wallos
Upstream: https://github.com/ellite/Wallos

---

## 1. Expiring Subscriptions View

### Problem
No easy way to see at a glance which subscriptions are not auto-renewing and when they expire. Everything is mixed together in the main list.

### Requirements
- Dedicated "Expiring" tab or filter in the main subscriptions view
- Shows only subscriptions where `auto_renew=0` and `inactive=0`
- Sorted by `next_payment` date ascending
- Visual indicator (badge/label) on the main list distinguishing expiring vs active subscriptions
- Optionally: color-code by urgency (e.g. red = expiring within 30 days, yellow = 30–90 days)

### Current Workaround
SQL query via CLI:
```sql
SELECT name, next_payment FROM subscriptions
WHERE auto_renew=0 AND user_id=1 AND inactive=0
ORDER BY next_payment;
```

### PR Candidate
Yes — straightforward UI filter, low risk, useful for all users.

---

## 2. Weekly Telegram Digest

### Problem
3-day notifications are good for immediate alerts but don't give a forward-looking view of what's coming up in the next month/quarter.

### Requirements
- Runs every Monday morning via cron
- Queries subscriptions expiring (auto_renew=0) in next 30, 60, and 90 days
- Sends a formatted Telegram message grouping by timeframe:
  - "This month (next 30 days): X, Y, Z"
  - "Next 60 days: A, B"
  - "Next 90 days: C"
- Also optionally summarizes upcoming auto-renewing subscriptions and their costs for the month
- Configurable lookahead window (30/60/90 days) in settings

### Current Workaround
None — relies on per-subscription 3-day notifications only.

### PR Candidate
Yes — extends existing notification infrastructure.

---

## 3. Recurring Payments (Non-Subscription)

### Problem
Wallos only supports subscriptions (services you choose). Many recurring financial obligations don't fit this model:
- School fees (daughter's tuition)
- Extracurricular classes (swimming, etc.)
- Rent / EMIs
- Insurance premiums
- Any fixed recurring payment to a person/institution

### Requirements
- New "Recurring Payments" section separate from Subscriptions
- Fields: payee name, amount, currency, frequency, next due date, category, notes
- Categories specific to payments: Education, Housing, Insurance, Loan/EMI, Activities, Other
- Same notification support as subscriptions (X days before due date)
- Included in monthly cost calculations and dashboard totals
- Optionally: distinguish in stats between "subscriptions" spend vs "obligations" spend

### Current Workaround
Could be hacked in as a subscription entry but semantically wrong and pollutes the subscription list.

### PR Candidate
Maybe — significant scope change. Discuss with maintainer before building. Could be a separate PR or a settings toggle to enable "payments mode".

---

## 4. Budget vs Actual by Category

### Problem
No way to set a spending limit per category and track against it. Easy to overspend on e.g. Investing newsletters without realising.

### Requirements
- Set monthly/annual budget per category (e.g. Investing: $500/year)
- Dashboard shows budget utilisation per category (progress bar style)
- Alert when a new subscription would push a category over budget
- Summary: total budgeted vs total actual spend

### PR Candidate
Yes — additive feature, doesn't break existing behaviour.

---

## 5. Family Cost Splitting View

### Problem
Household members exist in Wallos but there's no clear view of "who pays what" and shared cost breakdowns.

### Requirements
- Per-member spending summary (already partially exists in stats)
- Show shared subscriptions (e.g. YouTube Premium family split) with per-person cost
- "My share" vs "total cost" distinction
- Useful for household budgeting conversations

### Notes
- YouTube Premium: $26.16/month total, $8.72/month per person (3-way split)
- Currently tracked as $8.72 — full cost split logic would need to be built

### PR Candidate
Maybe — depends on how household feature is currently designed upstream.

---

## 6. Annual Spending Forecast

### Problem
No forward-looking view of when large payments hit across the year. October is heavy (multiple renewals) but this isn't visible.

### Requirements
- Monthly calendar/bar chart view showing total spend per month for the next 12 months
- Highlights months with unusually high spend
- Breakdown by subscription within each month
- Optionally: export as CSV

### PR Candidate
Yes — purely additive visualisation.

---

## 7. Cancellation Tracker

### Problem
For expiring subscriptions, there's no place to store how/where to cancel. Easy to forget the cancellation URL or steps before the renewal date hits.

### Requirements
- Extra field per subscription: "Cancellation URL" or "Cancellation notes"
- Shown prominently on expiring subscriptions
- Optionally included in the Telegram notification ("Cancel at: substack.com/account")

### PR Candidate
Yes — small additive field, clean PR.

---

## 8. INR / USD Toggle

### Problem
All subscriptions display in their native currency. No way to see everything normalised to one currency on demand without changing the main currency setting.

### Requirements
- Toggle button in the UI: "Show in USD" / "Show in INR"
- Uses existing exchange rates already stored in DB
- Affects display only, doesn't change stored values

### PR Candidate
Yes — display-only change, no DB schema changes needed.

---

## Priority Order (suggested)
1. Expiring subscriptions view — highest daily utility, easiest to build
2. Cancellation tracker — small effort, complements expiring view
3. Weekly Telegram digest — no UI needed, pure backend
4. Annual spending forecast — good visualisation, moderate effort
5. Budget vs actual — useful but requires more UX thought
6. Recurring payments — biggest scope, discuss with upstream first
7. Family cost splitting — dependent on household feature design
8. INR/USD toggle — nice to have
