# Personal Finance Skill for Clawdbot

## Product Vision
A Clawdbot skill that connects to European bank accounts via Open Banking, analyzes spending habits, generates visual reports, and delivers insights via Telegram/WhatsApp.

## Target User
Clawdbot users who want automated personal finance tracking without using separate apps.

## Core Requirements

### Must Have (MVP)
1. **Bank Connection** — OAuth flow via GoCardless/Nordigen (2,300+ EU banks)
2. **Transaction Sync** — Fetch and store transactions locally
3. **Auto-Categorization** — Classify transactions (groceries, dining, transport, etc.)
4. **Spending Charts** — Generate PNG charts optimized for mobile/chat
5. **Scheduled Reports** — Daily brief, weekly summary, monthly deep-dive
6. **Report Comparison** — Month-on-month comparisons, trend analysis
7. **Chat Delivery** — Send reports/charts via Telegram/WhatsApp

### Should Have
8. **Budget Tracking** — Set budgets per category, track progress
9. **Anomaly Detection** — Flag unusual transactions
10. **Multi-Account** — Support multiple bank connections
11. **Historical Storage** — Save reports for comparison

### Could Have (Future)
12. **Predictive Insights** — "At this rate, you'll overspend by..."
13. **Subscription Detection** — Identify recurring charges
14. **Goal Tracking** — Savings goals with progress
15. **Proactive Alerts** — "You've spent 50% more on dining this week"

## Technical Architecture

### Bank Integration
- **Provider**: GoCardless Bank Account Data (formerly Nordigen)
- **Auth**: OAuth 2.0 with PKCE
- **Token Storage**: macOS Keychain (keychain.py helper)
- **Refresh**: Automatic token refresh, 90-day re-consent

### Data Storage
- **Transactions**: SQLite database (`~/.config/clawdbot-finance/transactions.db`)
- **Reports**: Markdown files (`~/.config/clawdbot-finance/reports/`)
- **Charts**: Generated PNGs (temp, sent then deleted)

### Categorization
- **Primary**: Rule-based (merchant name patterns)
- **Fallback**: Simple keyword matching
- **User Override**: Allow manual recategorization

### Chart Generation
- **Library**: Python matplotlib or plotly
- **Output**: PNG optimized for mobile (max 800px width)
- **Types**: 
  - Pie chart (category breakdown)
  - Bar chart (daily/weekly spending)
  - Line chart (trends over time)
  - Progress bars (budget tracking)

### Report Formats

#### Daily Brief (sent 8am)
```
🌅 Daily Finance Brief — Jan 30, 2026

💰 Balances
• Main Account: €2,847.92
• Savings: €12,450.00

📊 Yesterday
Spent: €89.23 (4 transactions)
• Migros         €43.23 🛒
• SBB            €18.90 🚃
• Starbucks      €6.47  ☕
• Netflix        €15.99 📺

📈 vs. typical Tuesday: +€12 (normal)

[Chart: spending by category - sent as image]
```

#### Weekly Summary (Sunday 6pm)
```
📊 Weekly Finance Summary — Week 4, Jan 2026

💸 Total Spent: €487.23
   vs last week: -€52 (↓10%)

📂 By Category:
Groceries     €156.23  ████████░░  32%
Transport     €89.50   ████░░░░░░  18%
Dining        €78.90   ████░░░░░░  16%
Shopping      €67.40   ███░░░░░░░  14%
Subscriptions €45.20   ██░░░░░░░░   9%
Other         €50.00   ██░░░░░░░░  10%

🎯 Budget Status:
Dining: €78/€100 (78%) ⚠️ On track
Shopping: €67/€150 (45%) ✅ Under budget

[Chart: weekly trend - sent as image]
```

#### Monthly Deep-Dive (1st of month, 9am)
```
📈 Monthly Finance Report — January 2026

💰 Summary
Income:      €5,200.00
Expenses:    €3,847.23
Net:         +€1,352.77 (saved 26%)

📊 Top Categories:
1. Rent/Housing   €1,200.00  (31%)
2. Groceries      €623.45    (16%)
3. Transport      €312.80    (8%)
4. Dining Out     €298.50    (8%)
5. Utilities      €187.30    (5%)

📈 vs. December:
• Groceries: +€45 (+8%)
• Dining: -€87 (-23%) ✅
• Transport: +€12 (+4%)

🔍 Insights:
• Your dining spending dropped significantly
• Grocery costs rising - inflation or habits?
• 3 new subscriptions detected this month

[Charts: category pie, trend line, comparison bar - sent as images]
```

## Commands

| Command | Description |
|---------|-------------|
| `/finance setup` | Start bank connection OAuth flow |
| `/finance balance` | Show current balances |
| `/finance spending [period]` | Show spending (today/week/month) |
| `/finance report [type]` | Generate report (daily/weekly/monthly) |
| `/finance compare [month1] [month2]` | Compare two months |
| `/finance budget set <category> <amount>` | Set category budget |
| `/finance budget` | Show budget status |
| `/finance categorize <txn_id> <category>` | Recategorize transaction |
| `/finance accounts` | List connected accounts |
| `/finance sync` | Force transaction sync |

## Clawdbot Skill Structure

```
skills/
└── personal-finance/
    ├── SKILL.md           # Skill documentation
    ├── scripts/
    │   ├── setup.py       # OAuth flow handler
    │   ├── sync.py        # Transaction sync
    │   ├── categorize.py  # Transaction categorization
    │   ├── charts.py      # Chart generation
    │   ├── reports.py     # Report generation
    │   └── commands.py    # Command handlers
    ├── templates/
    │   ├── daily.md       # Daily report template
    │   ├── weekly.md      # Weekly report template
    │   └── monthly.md     # Monthly report template
    └── assets/
        └── categories.json # Category definitions
```

## Security Requirements

1. **No plaintext credentials** — All tokens in Keychain
2. **Local data only** — Transactions stored locally, not in cloud
3. **Encryption at rest** — SQLite with encryption (optional)
4. **Minimal permissions** — Read-only bank access (no payment initiation)
5. **User consent** — Clear explanation during OAuth flow

## Dependencies

- Python 3.10+
- `requests` — API calls
- `matplotlib` or `plotly` — Charts
- `sqlite3` — Data storage (built-in)
- Clawdbot's `keychain.py` for secure storage

## Success Metrics

1. Bank connection works for top 10 EU banks
2. Charts render correctly on mobile Telegram
3. Daily reports deliver reliably at scheduled time
4. Categorization accuracy > 80% without user training

## Open Questions

1. GoCardless free tier limits? (50 connections should be fine for personal use)
2. How to handle bank connection expiry (90 days)?
3. Should we support multiple currencies?
