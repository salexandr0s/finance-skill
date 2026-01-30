# Personal Finance Skill

Track your spending from European bank accounts (via CSV import) and crypto wallets (via Zerion API).

## Why CSV Import?

European Open Banking APIs (PSD2) require third-party providers to be **registered and regulated** - this means business registration, legal URLs, and compliance requirements. For personal finance tracking, this isn't practical.

CSV import is:
- **Private**: Your data never leaves your machine
- **Universal**: Works with any bank that exports CSV
- **Simple**: Just download and share your statement

## Quick Start

1. Run `/finance setup` to configure your first account
2. Download a CSV from your bank's online portal
3. Share the CSV file and run `/finance import <file>`
4. View spending with `/finance spending`

## Supported Banks

Format is auto-detected for **84 European banks** across 17 countries:

| Country | Banks |
|---------|-------|
| Switzerland | UBS, Credit Suisse, PostFinance, Raiffeisen, ZKB, BCV, BCGE, Migros Bank, Cler |
| Germany | Deutsche Bank, Sparkasse, Commerzbank, ING, DKB, N26, comdirect, Postbank, HypoVereinsbank, Volksbank, Targobank, Tomorrow |
| France | BNP Paribas, Société Générale, Crédit Agricole, Crédit Mutuel, La Banque Postale, LCL, Boursorama, Fortuneo, Caisse d'Épargne |
| UK | Barclays, HSBC, Lloyds, NatWest, RBS, Santander, Halifax, Monzo, Starling, Revolut, Nationwide |
| Netherlands | ING, Rabobank, ABN AMRO, SNS Bank, Triodos, bunq |
| Belgium | KBC, Belfius, ING, BNP Fortis, Argenta |
| Austria | Erste Bank, Raiffeisen, Bank Austria, BAWAG |
| Spain | Santander, BBVA, CaixaBank, Sabadell |
| Italy | Intesa Sanpaolo, UniCredit, BNL, Fineco |
| Portugal | CGD, Millennium BCP, Novo Banco |
| Ireland | AIB, Bank of Ireland, PTSB |
| Nordic | Nordea, OP Bank, Danske Bank, SEB, Swedbank, Handelsbanken, DNB |
| Poland | PKO BP, mBank, ING |
| Neobanks | Revolut, N26, Wise, Vivid |

Run `/finance import --list-banks` for the full list.

Don't see your bank? The generic format handles most standard CSV exports.

## Commands

### Bank Accounts

| Command | Description |
|---------|-------------|
| `/finance setup` | Initial setup wizard |
| `/finance import <file>` | Import transactions from CSV |
| `/finance import --list-banks` | List supported bank formats |
| `/finance accounts` | List all accounts |
| `/finance accounts remove --id <id>` | Remove an account |

### Spending & Analysis

| Command | Description |
|---------|-------------|
| `/finance spending [today\|week\|month]` | Spending summary |
| `/finance balance` | Account balances |
| `/finance report [daily\|weekly\|monthly]` | Detailed reports |
| `/finance compare <YYYY-MM> [YYYY-MM]` | Compare months |

### Budgets

| Command | Description |
|---------|-------------|
| `/finance budget set <category> <amount>` | Set monthly budget |
| `/finance budget show` | View budget status |
| `/finance categorize <txn_id> <category>` | Override category |

### Reminders

| Command | Description |
|---------|-------------|
| `/finance reminder status` | Check reminder settings |
| `/finance reminder enable` | Enable monthly reminders |
| `/finance reminder disable` | Disable reminders |
| `/finance reminder set-day --day <1-28>` | Set reminder day |

### Crypto Wallets

| Command | Description |
|---------|-------------|
| `/finance wallet add <address>` | Add wallet |
| `/finance wallet remove <address>` | Remove wallet |
| `/finance wallet show [--detailed]` | View balances |
| `/finance wallet sync` | Refresh data |
| `/finance wallet list` | List all wallets |

### Settings

| Command | Description |
|---------|-------------|
| `/finance currency [CODE]` | Set/show home currency |

## Features

### Multi-Account Support
Track multiple bank accounts and import CSVs into different accounts:
```
/finance import statement.csv --account "Main Checking"
/finance import savings.csv --account "Savings"
```

### Deduplication
Transactions are automatically deduplicated based on date, amount, and description. Import the same CSV twice and duplicates are skipped.

### Monthly Reminders
Get reminded at the end of each month to download and import your bank statements:
```
/finance reminder enable
/finance reminder set-day --day 28
```

### Auto-Categorization
Transactions are automatically categorized based on description patterns. Override any category with:
```
/finance categorize <transaction_id> groceries
```

### Spending Anomaly Detection
Unusual spending is automatically flagged when it exceeds 2x your historical average.

## Data Privacy

- All data is stored locally in `~/.config/clawdbot-finance/`
- No data is sent to external APIs (except Zerion for crypto)
- CSV files are processed locally
- Database file has restricted permissions (0o600)

## Requirements

- Python 3.8+
- requests (for crypto API)
- matplotlib (for charts)

Install dependencies:
```bash
pip install requests matplotlib
```

## File Structure

```
skills/personal-finance/
├── SKILL.md              # Skill metadata
├── scripts/
│   ├── finance.py        # Main entry point
│   ├── csv_import.py     # CSV import & bank formats
│   ├── db.py             # Database operations
│   ├── categorize.py     # Transaction categorization
│   ├── currency.py       # Currency conversion
│   ├── crypto.py         # Zerion wallet tracking
│   └── config.py         # Configuration
└── templates/
    ├── reports.py        # Report generation
    └── charts.py         # Chart generation
```

## License

MIT
