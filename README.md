# Personal Finance Skill

Track your spending, analyze habits, and get automated insights from your bank accounts and crypto wallets.

## Features

- **Bank Connection** — Connect 2,500+ European banks via Enable Banking Open Banking API
- **Crypto Wallets** — Track EVM (Ethereum, Polygon, etc.) and Solana wallets via Zerion
- **Multi-Currency** — All amounts displayed in your preferred currency
- **Smart Categorization** — Auto-categorize transactions with Swiss merchant database
- **Anomaly Detection** — Flag unusual spending (>2x category average)
- **Visual Reports** — Mobile-optimized charts for Telegram/WhatsApp
- **Budget Tracking** — Set limits and monitor progress

## Quick Start

```bash
# Install dependencies
pip install requests matplotlib pyjwt

# Run the setup wizard
python skills/personal-finance/scripts/finance.py setup
```

The setup wizard will guide you through:
1. Getting Enable Banking API credentials
2. Connecting your bank account
3. Setting your home currency
4. Adding crypto wallets (optional)

## API Keys

This skill uses two external APIs. Both have free tiers.

### Enable Banking (Required for banking)

Provides access to 2,500+ European banks across 29 countries via Open Banking.

| | |
|---|---|
| **Sign up** | https://enablebanking.com/sign-in/ |
| **Get credentials** | Control Panel → API Applications → Register new app |
| **Free tier** | Sandbox (auto-activated), Production (requires verification) |
| **What you need** | `Application ID` and private key (.pem file) |

### Zerion API (Required for crypto wallets)

Provides portfolio data for EVM chains and Solana.

| Plan | Requests/Day | Cost | Best For |
|------|-------------|------|----------|
| **Demo** (default) | 300 | Free | Testing |
| **Developer** | 2,000 | Free | Personal use |
| **Growth** | 1,000,000 | $499/mo | Production apps |

| | |
|---|---|
| **Sign up** | https://developers.zerion.io |
| **Get API key** | Dashboard → API Keys |
| **Recommendation** | Sign up for free **Developer** key for 2,000 requests/day |

## Commands

| Command | Description |
|---------|-------------|
| `/finance setup` | Interactive setup wizard |
| `/finance connect` | Connect additional bank account |
| `/finance balance` | Show account balances |
| `/finance spending [today/week/month]` | Spending summary |
| `/finance report [daily/weekly/monthly]` | Generate report with chart |
| `/finance sync` | Refresh transaction data |
| `/finance compare <month1> [month2]` | Compare spending between months |
| `/finance currency [code]` | Set or show home currency |
| `/finance budget set <category> <amount>` | Set monthly budget |
| `/finance budget show` | Show budget progress |
| `/finance wallet add <address>` | Add crypto wallet |
| `/finance wallet show` | Show crypto balances |
| `/finance wallet sync` | Refresh crypto data |
| `/finance accounts` | List connected accounts |

## Architecture

```
skills/personal-finance/
├── SKILL.md              # Full documentation
├── scripts/
│   ├── finance.py        # Main CLI entry point
│   ├── enablebanking.py  # Enable Banking API client
│   ├── crypto.py         # Zerion API client
│   ├── currency.py       # Multi-currency conversion
│   ├── db.py             # SQLite database
│   ├── categorize.py     # Transaction categorization
│   ├── charts.py         # Chart generation
│   └── config.py         # Configuration settings
├── templates/
│   └── reports.py        # Report generation
├── config/
│   └── categories.json   # Category rules
└── test_setup.py         # Test suite
```

## Security

- **Read-only bank access** — Cannot initiate payments
- **Local storage** — All data stays on your machine
- **Encrypted credentials** — Stored in macOS Keychain (file fallback with 0600 permissions)
- **Rate limiting** — Respects API limits

## Data Storage

| Data | Location |
|------|----------|
| Transactions | `~/.config/clawdbot-finance/transactions.db` |
| Charts | `~/.config/clawdbot-finance/charts/` |
| Reports | `~/.config/clawdbot-finance/reports/` |
| Enable Banking credentials | macOS Keychain or `~/.config/enablebanking_creds.json` |
| Zerion credentials | macOS Keychain or `~/.config/zerion_creds.json` |

## Testing

```bash
cd skills/personal-finance
python test_setup.py
```

Expected output: `10/10 tests passed`

## License

MIT
