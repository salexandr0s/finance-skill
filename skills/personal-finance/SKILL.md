---
name: personal-finance
description: Personal finance tracking via GoCardless Open Banking. Syncs transactions, auto-categorizes spending, generates charts and reports.
homepage: https://developer.gocardless.com/bank-account-data/
metadata: 
  clawdbot:
    emoji: 💰
    os: [darwin]
    requires:
      python: ["requests", "matplotlib"]
    commands:
      - /finance
---

# 💰 Personal Finance

Track your spending, analyze habits, and get automated insights from your European bank accounts via Open Banking.

## Features

✅ **Bank Connection** — Connect 2,300+ European banks via GoCardless  
✅ **Auto-Sync** — Fetch transactions automatically with rate limiting  
✅ **Smart Categorization** — Auto-categorize with Swiss merchant database  
✅ **Anomaly Detection** — Flag unusual spending (>2x category average)  
✅ **Visual Reports** — Mobile-optimized charts for Telegram/WhatsApp  
✅ **Budget Tracking** — Set limits and monitor progress  
✅ **Scheduled Reports** — Daily, weekly, monthly summaries  

## Quick Start (Recommended)

The easiest way to get started is with the interactive setup wizard:

```
/finance setup
```

This guided wizard will:
1. **Get API credentials** — Walk you through creating a free GoCardless account
2. **Connect your bank** — Help you authenticate with your bank (read-only access)
3. **Set your currency** — Choose your home currency for consistent display

That's it! After setup, your transactions will sync automatically.

---

## Manual Setup (Alternative)

If you prefer manual configuration:

### 1. Get GoCardless Credentials

1. Sign up at https://bankaccountdata.gocardless.com (free tier available)
2. Go to https://bankaccountdata.gocardless.com/user-secrets/
3. Create a new secret and note the `secret_id` and `secret_key`

### 2. Store Credentials

```bash
# Interactive setup
python ~/.config/clawdbot/skills/personal-finance/scripts/gocardless.py setup

# Or manual keychain storage (adjust path to your installation)
python -c "
import sys, os; sys.path.append(os.path.expanduser('~/.config/clawdbot'))
from keychain import set_key
set_key('gocardless_secret_id', 'your_secret_id_here')
set_key('gocardless_secret_key', 'your_secret_key_here')
"
```

### 3. Connect Your Bank

```
/finance setup
# Follow the link to authenticate with your bank
# Check connection status with: /finance accounts
```

### 4. Set Home Currency (Optional)

```
/finance currency EUR
# All amounts will be displayed in your chosen currency
```

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/finance setup` | Interactive onboarding wizard | `/finance setup` |
| `/finance balance` | Show current account balances | `/finance balance` |
| `/finance spending [period]` | Show spending summary | `/finance spending week` |
| `/finance report [type]` | Generate detailed report with chart | `/finance report monthly` |
| `/finance sync [--force]` | Force transaction sync | `/finance sync` |
| `/finance budget set <category> <amount>` | Set monthly budget | `/finance budget set dining 300` |
| `/finance budget show` | Show budget progress | `/finance budget show` |
| `/finance categorize <txn_id> <category>` | Override transaction category | `/finance categorize abc123 groceries` |
| `/finance accounts` | List connected accounts | `/finance accounts` |
| `/finance compare <month1> [month2]` | Compare spending between months | `/finance compare 2026-01 2025-12` |
| `/finance currency [code]` | Set or show home currency | `/finance currency EUR` |
| `/finance wallet add <address>` | Add crypto wallet | `/finance wallet add 0x123... --chain ethereum` |
| `/finance wallet remove <address>` | Remove crypto wallet | `/finance wallet remove 0x123...` |
| `/finance wallet show` | Show crypto balances | `/finance wallet show --detailed` |
| `/finance wallet sync` | Refresh crypto data | `/finance wallet sync` |
| `/finance wallet list` | List all wallets | `/finance wallet list` |

## Spending Periods

- `today` — Today's spending
- `week` — Current week (Monday-Sunday)  
- `month` — Current month

## Report Types

- `daily` — Balance summary + yesterday's transactions
- `weekly` — Category breakdown + budget status + daily trend
- `monthly` — Full analysis with insights + month-over-month comparison

## Categories

Default categories with Swiss merchant detection:

🛒 **Groceries** — Migros, Coop, Manor, Denner, Aldi, Lidl, Volg  
🍽️ **Dining** — Restaurants, cafes, takeaway, delivery  
🚃 **Transport** — SBB, ZVV, taxis, parking, fuel, Mobility  
🛍️ **Shopping** — Amazon, Zalando, electronics, furniture, fashion  
📺 **Subscriptions** — Netflix, Spotify, software, recurring services  
⚡ **Utilities** — Swisscom, electricity, insurance, phone bills  
🎮 **Entertainment** — Cinema, concerts, games, tickets  
🏥 **Health** — Pharmacy, doctors, fitness, medical  
🏠 **Housing** — Rent, mortgage, maintenance, furniture  
↔️ **Transfers** — TWINT, PayPal, bank transfers  
💰 **Income** — Salary, bonuses, dividends, refunds  

## Multi-Currency Support

If you have accounts in multiple currencies, set your "home currency" to see all amounts converted:

```
/finance currency EUR
# Now all amounts show in EUR with conversions
```

Features:
- **Automatic conversion** — Transactions in any currency show converted amounts
- **Exchange rate caching** — Rates cached for 24 hours (Frankfurter API, free)
- **30+ currencies** — EUR, USD, GBP, CHF, JPY, and many more
- **Historical rates** — Uses transaction date for accurate conversion

Example output:
```
🛒 Groceries: 45.50 CHF (€42.32)
🍽️ Dining: $28.99 (€26.78)
```

## Crypto Wallet Tracking

Track your crypto portfolio alongside bank accounts using the Zerion API.

### Supported Blockchains

Ethereum, Solana, Polygon, Arbitrum, Optimism, Base, Avalanche, BSC, Fantom, zkSync, Linea, and more.

### Setup

1. Get a free Zerion API key at https://developers.zerion.io
2. Add wallets during `/finance setup` or anytime with:

```bash
/finance wallet add 0xYourAddress --chain ethereum --label "Main Wallet"
/finance wallet add SolanaAddress --chain solana --label "Solana Trading"
```

### Wallet Commands

```bash
# Add a wallet
/finance wallet add <address> --chain <blockchain> --label "Name"

# View all wallet balances
/finance wallet show

# View with token breakdown
/finance wallet show --detailed

# Refresh wallet data
/finance wallet sync

# List configured wallets
/finance wallet list

# Remove a wallet
/finance wallet remove <address>
```

### Reports Integration

Monthly reports automatically include crypto holdings:

```
🪙 Crypto Holdings:
• Main Wallet: €4,234.56 ($4,612.00)
• Solana Trading: €1,890.23 ($2,059.15)
Total Crypto: €6,124.79

💎 Total Assets:
Bank Accounts:    12,500 CHF
Crypto:            6,125 CHF
Total:            18,625 CHF
```

## Anomaly Detection

Automatically flags transactions that are **>2x the average** for that category based on historical data (last 6 periods).

Example: If you typically spend 50 CHF on groceries, a 120 CHF grocery transaction will be flagged.

## Scheduled Reports

Set up automatic delivery:

```bash
# Daily report at 8 AM
clawdbot cron add "finance-daily" "0 8 * * *" \
  --model sonnet \
  "Generate daily finance report: python ~/.config/clawdbot/skills/personal-finance/scripts/finance.py report daily"

# Weekly report Sunday 6 PM  
clawdbot cron add "finance-weekly" "0 18 * * 0" \
  --model sonnet \
  "Generate weekly finance report: python ~/.config/clawdbot/skills/personal-finance/scripts/finance.py report weekly"

# Monthly report 1st at 9 AM
clawdbot cron add "finance-monthly" "0 9 1 * *" \
  --model sonnet \
  "Generate monthly finance report: python ~/.config/clawdbot/skills/personal-finance/scripts/finance.py report monthly"
```

## Data Storage

- **Transactions:** `~/.config/clawdbot-finance/transactions.db` (SQLite)
- **Charts:** `~/.config/clawdbot-finance/charts/` (PNG files, auto-cleanup)
- **Reports:** `~/.config/clawdbot-finance/reports/` (Markdown archives)
- **Categories:** `skills/personal-finance/config/categories.json`

All credentials stored in macOS Keychain (never plain text).

## Privacy & Security

✅ **Read-only access** — Cannot initiate payments  
✅ **Local storage** — All data stays on your machine  
✅ **Encrypted credentials** — Keychain integration  
✅ **Rate limiting** — Respects bank API limits  
✅ **90-day re-auth** — Automatic expiry reminders  

## Supported Banks

2,300+ European banks via PSD2 Open Banking including:

**Switzerland:** UBS, Credit Suisse, PostFinance, Raiffeisen, ZKB, Revolut  
**Germany:** Deutsche Bank, Commerzbank, DKB, ING, N26  
**UK:** Barclays, HSBC, Lloyds, Monzo, Starling  
**France:** BNP Paribas, Crédit Agricole, Société Générale  

Full list: https://docs.google.com/spreadsheets/d/1EZ5n7QDGaRIot5M86dwqd5UFSGEDTeTRzEq3D9uEDkM/

## Rate Limits

- **Conservative approach:** Max 3 API calls per day per account
- **Automatic backoff:** Respects `Retry-After` headers  
- **Graceful degradation:** Shows cached data when limits hit
- **Force override:** Use `--force` flag in emergencies

## Example Usage

```bash
# Initial setup
/finance setup
# → Follow OAuth link, authenticate with bank

# Check balance
/finance balance
# → 💰 Account Balances
# → • UBS Main: 2,847.92 CHF
# → • Savings: 12,450.00 CHF

# Weekly spending
/finance spending week
# → 💸 Spending Summary - Week
# → 🛒 Groceries: 156.23 CHF (32%)
# → 🍽️ Dining: 78.90 CHF (16%)
# → ⚠️ Anomalies Detected:
# → • Dining: 78.90 CHF (+58% vs average)

# Generate report with chart
/finance report monthly
# → [Generates detailed report + pie chart]
```

## Troubleshooting

**Connection Issues:**
```bash
# Check account status
/finance accounts

# Force re-authentication
/finance setup

# Manual token refresh
python ~/.config/clawdbot/skills/personal-finance/scripts/gocardless.py setup
```

**Rate Limiting:**
- Wait until next day for automatic reset
- Use `/finance sync --force` sparingly
- Check limits: banks allow 3-4 calls per day per endpoint

**Missing Transactions:**
- Run `/finance sync` to fetch latest data
- Check date range — some banks limit historical access
- Verify account is still connected in `/finance accounts`

**Categorization Issues:**
- Override specific transactions: `/finance categorize <id> <category>`
- Patterns are case-insensitive and support partial matches
- Add custom rules by editing `config/categories.json`

## Development

The skill consists of:

- **finance.py** — Main CLI entry point with commands
- **gocardless.py** — GoCardless API client with auth flow
- **crypto.py** — Zerion API client for crypto wallets
- **db.py** — SQLite operations with secure storage
- **categorize.py** — Rule-based transaction categorization
- **currency.py** — Multi-currency conversion (Frankfurter API)
- **charts.py** — Mobile-optimized chart generation
- **config.py** — Centralized configuration settings
- **templates/reports.py** — Report generation with crypto + currency support

Charts use matplotlib with mobile-friendly settings (800px width, readable fonts).

## Dependencies

```python
# Required packages
requests>=2.31.0    # API calls
matplotlib>=3.8.0   # Chart generation

# Built-in
sqlite3             # Database
json               # Config files
datetime           # Date handling
pathlib            # File operations
```

Install with: `pip install requests matplotlib`

---

**GoCardless Bank Account Data** integration provides secure, read-only access to your financial data via regulated Open Banking APIs. No card details or payment capabilities — purely for tracking and analysis.

**Legal:** This skill accesses financial data via your explicit consent through regulated PSD2 Open Banking protocols. Data processing occurs locally on your device.