---
name: personal-finance
description: Personal finance tracking via CSV import from European banks. Imports transactions, auto-categorizes spending, generates charts and reports. Monthly reminders to import new statements.
homepage: https://github.com/salexandr0s/finance-skill
metadata:
  clawdbot:
    emoji:
    os: [darwin, linux]
    requires:
      python: ["requests", "matplotlib"]
    commands:
      - /finance
---

# Personal Finance

Track your spending from European bank accounts via CSV import and crypto wallets via Zerion API.

## Why CSV Import?

European Open Banking APIs (PSD2) require third-party providers to be **registered and regulated** - this means business registration, legal documentation, and compliance requirements. For personal finance tracking, this isn't practical.

CSV import is:
- **Private** - Your data never leaves your machine
- **Universal** - Works with any bank that exports CSV
- **Simple** - Just download and share your statement
- **Reliable** - No API keys, OAuth flows, or token expiry

## Features

- **CSV Import** - Auto-detect format for 20+ European banks
- **Multi-Account** - Track multiple bank accounts separately
- **Deduplication** - Import same CSV twice without duplicates
- **Monthly Reminders** - Get reminded to import new statements
- **Smart Categorization** - Auto-categorize with merchant patterns
- **Subscription Tracking** - Track recurring payments with totals
- **Anomaly Detection** - Flag unusual spending (>2x average)
- **Visual Reports** - Charts for spending breakdown
- **Budget Tracking** - Set limits and monitor progress
- **Crypto Wallets** - Track EVM and Solana wallets via Zerion

## Quick Start

The easiest way to get started:

```
/finance setup
```

This guided wizard will:
1. **Set your currency** - Choose EUR, USD, CHF, GBP, etc.
2. **Create an account** - Name your first bank account
3. **Enable reminders** - Get monthly prompts to import CSVs
4. **Add crypto** (optional) - Connect Zerion for wallet tracking

After setup:
1. Download a CSV from your bank's online portal
2. Share the file and run `/finance import <file>`
3. View spending with `/finance spending`

## Supported Banks

Format is auto-detected from CSV headers. **84 banks** supported across 17 European countries:

| Country | Banks |
|---------|-------|
| **Switzerland** (9) | UBS, Credit Suisse, PostFinance, Raiffeisen, ZKB, BCV, BCGE, Migros Bank, Bank Cler |
| **Germany** (12) | Deutsche Bank, Sparkasse, Commerzbank, ING, DKB, N26, comdirect, Postbank, HypoVereinsbank, Volksbank, Targobank, Tomorrow |
| **France** (9) | BNP Paribas, Société Générale, Crédit Agricole, Crédit Mutuel, La Banque Postale, LCL, Boursorama, Fortuneo, Caisse d'Épargne |
| **UK** (11) | Barclays, HSBC, Lloyds, NatWest, RBS, Santander, Halifax, Monzo, Starling, Revolut, Nationwide |
| **Netherlands** (6) | ING, Rabobank, ABN AMRO, SNS Bank, Triodos, bunq |
| **Belgium** (5) | KBC, Belfius, ING, BNP Fortis, Argenta |
| **Austria** (4) | Erste Bank, Raiffeisen, Bank Austria, BAWAG |
| **Spain** (4) | Santander, BBVA, CaixaBank, Sabadell |
| **Italy** (4) | Intesa Sanpaolo, UniCredit, BNL, FinecoBank |
| **Portugal** (3) | CGD, Millennium BCP, Novo Banco |
| **Ireland** (3) | AIB, Bank of Ireland, Permanent TSB |
| **Finland** (2) | Nordea, OP Bank |
| **Denmark** (1) | Danske Bank |
| **Sweden** (3) | SEB, Swedbank, Handelsbanken |
| **Norway** (1) | DNB |
| **Poland** (3) | PKO BP, mBank, ING |
| **Neobanks** (4) | Revolut, N26, Wise, Vivid Money |

Run `/finance import --list-banks` for the complete list with format keys.

Don't see your bank? Try anyway - the `generic` format handles most standard CSV exports with columns like Date, Amount, Description.

## Commands

### Setup & Import

| Command | Description | Example |
|---------|-------------|---------|
| `/finance setup` | Interactive setup wizard | `/finance setup` |
| `/finance import <file>` | Import transactions from CSV | `/finance import ~/Downloads/statement.csv` |
| `/finance import --list-banks` | List supported bank formats | `/finance import --list-banks` |
| `/finance import <file> --bank <format>` | Force specific bank format | `/finance import stmt.csv --bank deutsche_bank` |
| `/finance import <file> --account <name>` | Import to specific account | `/finance import stmt.csv --account Savings` |

### Accounts

| Command | Description |
|---------|-------------|
| `/finance accounts` | List all accounts with stats |
| `/finance accounts remove --id <id>` | Remove account and transactions |

### Spending & Reports

| Command | Description | Example |
|---------|-------------|---------|
| `/finance spending [period]` | Spending summary | `/finance spending month` |
| `/finance balance` | Account totals | `/finance balance` |
| `/finance report [type]` | Detailed report with chart | `/finance report monthly` |
| `/finance compare <month1> [month2]` | Compare months | `/finance compare 2026-01 2025-12` |

Periods: `today`, `week`, `month`
Report types: `daily`, `weekly`, `monthly`

### Budgets

| Command | Description | Example |
|---------|-------------|---------|
| `/finance budget set <category> <amount>` | Set monthly budget | `/finance budget set dining 300` |
| `/finance budget show` | Show budget progress | `/finance budget show` |
| `/finance categorize <txn_id> <category>` | Override category | `/finance categorize abc123 groceries` |

### Reminders

| Command | Description |
|---------|-------------|
| `/finance reminder status` | Check reminder settings |
| `/finance reminder enable` | Enable monthly reminders |
| `/finance reminder disable` | Disable reminders |
| `/finance reminder set-day --day <1-28>` | Set reminder day |

### Subscriptions

Track recurring payments like Netflix, Spotify, Claude, etc.

| Command | Description | Example |
|---------|-------------|---------|
| `/finance subscriptions list` | View all subscriptions with totals | `/finance subscriptions list` |
| `/finance subscriptions add <name> <amount>` | Add a subscription | `/finance subscriptions add Netflix 15.99` |
| `/finance subscriptions add ... --cycle <cycle>` | Set billing cycle | `/finance subscriptions add Spotify 9.99 --cycle monthly` |
| `/finance subscriptions add ... --currency <code>` | Set currency | `/finance subscriptions add Claude 20 --currency USD` |
| `/finance subscriptions remove <id>` | Remove a subscription | `/finance subscriptions remove 3` |
| `/finance subscriptions pause <id>` | Pause tracking | `/finance subscriptions pause 2` |
| `/finance subscriptions resume <id>` | Resume tracking | `/finance subscriptions resume 2` |
| `/finance subscriptions detect` | Auto-detect from transactions | `/finance subscriptions detect` |
| `/finance subscriptions detect --add` | Auto-add detected subscriptions | `/finance subscriptions detect --add` |

Billing cycles: `weekly`, `monthly`, `quarterly`, `yearly`

Categories are auto-detected from subscription name:
- **Streaming**: Netflix, Spotify, Disney+, YouTube, etc.
- **AI & Productivity**: Claude, ChatGPT, GitHub, Notion, etc.
- **Gaming**: PlayStation, Xbox, Nintendo, etc.
- **News**: NYT, Economist, Bloomberg, etc.
- **Fitness**: Strava, Headspace, Peloton, etc.

### Crypto Wallets

| Command | Description | Example |
|---------|-------------|---------|
| `/finance wallet add <address>` | Add wallet | `/finance wallet add 0x123... --chain ethereum` |
| `/finance wallet remove <address>` | Remove wallet | `/finance wallet remove 0x123...` |
| `/finance wallet show` | Show balances | `/finance wallet show --detailed` |
| `/finance wallet sync` | Refresh data | `/finance wallet sync` |
| `/finance wallet list` | List wallets | `/finance wallet list` |

### Settings

| Command | Description | Example |
|---------|-------------|---------|
| `/finance currency [code]` | Set/show currency | `/finance currency EUR` |

## Categories

Default categories with merchant detection:

| Category | Examples |
|----------|----------|
| Groceries | Migros, Coop, Aldi, Lidl, supermarkets |
| Dining | Restaurants, cafes, delivery |
| Transport | SBB, trains, taxis, fuel, parking |
| Shopping | Amazon, Zalando, retail |
| Subscriptions | Netflix, Spotify, recurring |
| Utilities | Phone, electricity, insurance |
| Entertainment | Cinema, concerts, games |
| Health | Pharmacy, doctors, fitness |
| Housing | Rent, mortgage, maintenance |
| Transfers | TWINT, PayPal, bank transfers |
| Income | Salary, refunds, deposits |

Override any transaction:
```
/finance categorize <transaction_id> groceries
```

## Multi-Account Support

Track multiple accounts separately:

```
/finance import checking.csv --account "Main Checking"
/finance import savings.csv --account "Savings"
/finance import credit.csv --account "Credit Card"
```

View all accounts:
```
/finance accounts
```

## Deduplication

Transactions are deduplicated based on:
- Date
- Amount
- Description (normalized)

Import the same CSV multiple times - duplicates are automatically skipped.

## Monthly Reminders

Get reminded at the end of each month to download your bank statements:

```
/finance reminder enable
/finance reminder set-day --day 28
```

On day 28, you'll see:
```
Monthly Finance Import Reminder - January 2026

It's time to download and import your bank statements!

Your accounts:
  - Main Checking - Last transaction: 2025-12-28
  - Savings - Last transaction: 2025-12-15

To import:
1. Download CSV from your bank's online portal
2. Share the CSV file with me
3. I'll import and categorize your transactions
```

## Crypto Wallet Tracking

Track crypto alongside bank accounts using Zerion API.

### Supported Chains
Ethereum, Solana, Polygon, Arbitrum, Optimism, Base, Avalanche, BSC, Fantom, zkSync, Linea, and more.

### Setup

1. Get a Zerion API key at https://developers.zerion.io
   - Demo key (default): 300 requests/day
   - Developer key (free): 2,000 requests/day

2. Add wallets:
```
/finance wallet add 0xYourAddress --chain ethereum --label "Main"
/finance wallet add SolanaAddress --chain solana --label "Trading"
```

## Data Storage

| Data | Location |
|------|----------|
| Transactions | `~/.config/clawdbot-finance/transactions.db` |
| Charts | `~/.config/clawdbot-finance/charts/` |
| Reports | `~/.config/clawdbot-finance/reports/` |
| Zerion credentials | macOS Keychain or `~/.config/zerion_creds.json` |

## Privacy & Security

- **Local processing** - CSV parsed locally, data never uploaded
- **No API keys for banking** - Pure CSV import, no OAuth
- **Restricted permissions** - Database file is 0600
- **Secure credential storage** - Keychain for crypto API keys

## Dependencies

```
requests>=2.31.0    # Crypto API calls
matplotlib>=3.8.0   # Chart generation
```

Install: `pip install requests matplotlib`

## Example Session

```
# Initial setup
/finance setup

# Download CSV from bank website, then:
/finance import ~/Downloads/ubs_statement.csv
# → Bank format: UBS (Switzerland)
# → Total rows: 156
# → Imported: 156 new transactions
# → Duplicates skipped: 0

# View spending
/finance spending month
# → Spending Summary - Month
# → [G] Groceries      1,234.56   32%  ======
# → [D] Dining           456.78   12%  ==
# → [T] Transport        234.56    6%  =
# → ...

# Set a budget
/finance budget set dining 400

# Next month - import again
/finance import ~/Downloads/ubs_feb.csv
# → Imported: 142 new transactions
# → Duplicates skipped: 14

# Compare months
/finance compare 2026-02 2026-01
```

## Troubleshooting

**CSV not recognized?**
- Try: `/finance import file.csv --bank generic`
- Check file encoding (UTF-8 or ISO-8859-1)
- Ensure file has headers

**Duplicates not detected?**
- Deduplication uses date + amount + description
- If bank changes description format, duplicates may slip through

**Wrong category?**
- Override: `/finance categorize <id> <category>`
- Categories are based on description patterns

---

## Agent Behavior

When this skill is active, the agent should proactively:

### Monthly Reminder Check
At the start of each conversation (especially near end of month), check if it's time to remind the user to import their bank statements:

```python
from csv_import import should_send_reminder, get_reminder_message, mark_reminder_sent

should_send, reason = should_send_reminder()
if should_send:
    message = get_reminder_message()
    # Display the reminder to the user
    mark_reminder_sent()  # Mark as sent so we don't repeat
```

If the reminder system is not yet configured and the user has bank accounts set up, ask:

> "Would you like me to remind you at the end of each month to download and import your latest bank statements? I can send you a reminder around day 25-28 of each month."

### After First Import
After the user successfully imports their first CSV file, offer to set up monthly reminders:

> "Great! I've imported your transactions. Would you like me to remind you each month to download your latest bank statements? This helps keep your spending data up to date."

### Proactive Spending Insights
When the user imports new transactions, proactively offer insights:
- Show a quick spending summary for the imported period
- Flag any unusual spending (anomalies)
- Compare to previous month if data available

### End of Month Check
Around day 25-28 of each month, if the user has configured accounts but hasn't imported recent data, proactively ask:

> "I noticed your last bank import was from [date]. Would you like to download and import your latest statements? I can help you track your spending for this month."

---

**Note:** This skill uses CSV import because European Open Banking APIs require regulated third-party provider status. CSV works reliably with any bank and keeps your data fully private.
