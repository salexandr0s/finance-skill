# Personal Finance Skill — Implementation Plan

## Executive Summary

This document provides a complete implementation roadmap for the Clawdbot personal finance skill. The skill connects to European bank accounts via GoCardless Bank Account Data API (formerly Nordigen), syncs transactions to a local SQLite database, auto-categorizes spending, generates mobile-optimized charts, and delivers scheduled reports via Telegram/WhatsApp.

**Estimated Total Effort:** 20-30 hours for full MVP

---

## 1. GoCardless Bank Account Data API — Research Summary

### 1.1 Authentication Flow

The API does NOT use OAuth2 in the traditional sense. Instead:

1. **Get User Secrets** — Create `secret_id` + `secret_key` in the [Bank Account Data portal](https://bankaccountdata.gocardless.com/user-secrets/)
2. **Create Refresh Token** — `POST /api/v2/token/new/` with secrets → get `refresh` token (30-day validity)
3. **Get Access Token** — `POST /api/v2/token/refresh/` with refresh token → get `access` token (24-hour validity)

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  User Secrets    │ ───► │  Refresh Token   │ ───► │  Access Token    │
│  (portal, once)  │      │  (30 days)       │      │  (24 hours)      │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

**Token Storage Requirements:**
- `secret_id` / `secret_key` → macOS Keychain (one-time setup)
- `refresh_token` + expiry → Keychain (refresh every 30 days)
- `access_token` + expiry → Keychain or memory (refresh hourly/as-needed)

### 1.2 Bank Connection Flow

```
1. List institutions      GET  /api/v2/institutions/?country=CH
2. Create agreement       POST /api/v2/agreements/enduser/
3. Create requisition     POST /api/v2/requisitions/
4. User clicks link       → Bank's OAuth page (hosted by bank)
5. User redirected back   → Our redirect URL with success/error
6. List accounts          GET  /api/v2/requisitions/{id}/
7. Fetch data             GET  /api/v2/accounts/{account_id}/{endpoint}
```

**Critical constraints:**
- **90-day re-authentication**: Default consent lasts 90 days, then user must re-link
- **Up to 730 days** possible with some banks (via `max_access_valid_for_days_reconfirmation`)
- **Bank-specific rate limits**: As low as 4 calls/day per endpoint per account
- **Read-only**: No payment initiation (AIS only, not PIS)

### 1.3 Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/token/new/` | POST | Get initial refresh token |
| `/api/v2/token/refresh/` | POST | Exchange refresh → access token |
| `/api/v2/institutions/?country={cc}` | GET | List available banks |
| `/api/v2/agreements/enduser/` | POST | Create end-user agreement |
| `/api/v2/requisitions/` | POST | Create link for bank auth |
| `/api/v2/requisitions/{id}/` | GET | Get requisition status + accounts |
| `/api/v2/accounts/{id}/details/` | GET | Account holder info, IBAN |
| `/api/v2/accounts/{id}/balances/` | GET | Current/available balances |
| `/api/v2/accounts/{id}/transactions/` | GET | Transaction history |

### 1.4 Rate Limits

**General API rate limits:**
- Headers: `HTTP_X_RATELIMIT_LIMIT`, `HTTP_X_RATELIMIT_REMAINING`, `HTTP_X_RATELIMIT_RESET`

**Per-account endpoint limits (bank-imposed):**
- Headers: `HTTP_X_RATELIMIT_ACCOUNT_SUCCESS_*`
- Can be as low as 4 requests/day per endpoint
- Strategy: Sync once daily, cache aggressively

**Free tier:**
- Unlimited connections
- "Non-verified" status badge shown to users (cosmetic only)
- Full API access

### 1.5 Transaction Data Format

```json
{
  "transactions": {
    "booked": [
      {
        "transactionId": "2024012900001",
        "bookingDate": "2024-01-29",
        "valueDate": "2024-01-29",
        "transactionAmount": {
          "amount": "-45.50",
          "currency": "CHF"
        },
        "creditorName": "MIGROS ZURICH",
        "remittanceInformationUnstructured": "Kartenzahlung Migros"
      }
    ],
    "pending": [...]
  }
}
```

Key fields for categorization:
- `creditorName` / `debtorName` — Merchant/counterparty name
- `remittanceInformationUnstructured` — Free-text description
- `merchantCategoryCode` — MCC code (not always present)

---

## 2. Chart Generation for Mobile Messaging

### 2.1 Technical Approach

**Library:** matplotlib (simpler, well-documented, sufficient for our needs)

**Output specs:**
- Format: PNG (best compression/quality for photos)
- Width: 800px (fits mobile screens without scaling)
- Height: 400-600px depending on chart type
- DPI: 100 (800px ÷ 8 inches = 100 DPI)

**Figure size formula:** `figsize = (width_px / dpi, height_px / dpi)`

### 2.2 Mobile-Optimized Settings

```python
import matplotlib.pyplot as plt
from io import BytesIO

def create_mobile_chart():
    # 800x400 pixels at 100 DPI
    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    
    # Mobile-friendly settings
    plt.rcParams.update({
        'font.size': 12,           # Readable on small screens
        'axes.titlesize': 14,      # Slightly larger titles
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 10,
        'figure.facecolor': 'white',
        'axes.facecolor': 'white',
        'axes.edgecolor': '#333333',
        'text.color': '#333333',
    })
    
    # ... draw chart ...
    
    # Save to BytesIO for sending
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf
```

### 2.3 Chart Types & Sizing

| Chart Type | Purpose | Recommended Size |
|------------|---------|------------------|
| Pie chart | Category breakdown | 800×600 (square-ish) |
| Horizontal bar | Category comparison | 800×400 |
| Vertical bar | Daily/weekly spending | 800×400 |
| Line chart | Trends over time | 800×400 |
| Progress bars | Budget tracking | 800×300 |

### 2.4 Color Palette

Consistent, accessible colors for categories:

```python
CATEGORY_COLORS = {
    'groceries':     '#2ecc71',  # Green
    'dining':        '#e74c3c',  # Red
    'transport':     '#3498db',  # Blue
    'shopping':      '#9b59b6',  # Purple
    'subscriptions': '#f39c12',  # Orange
    'utilities':     '#1abc9c',  # Teal
    'entertainment': '#e91e63',  # Pink
    'health':        '#00bcd4',  # Cyan
    'housing':       '#795548',  # Brown
    'other':         '#95a5a6',  # Gray
}
```

---

## 3. File Structure

Following Clawdbot skill conventions:

```
skills/
└── personal-finance/
    ├── SKILL.md                    # Skill documentation (required)
    ├── pyproject.toml              # Python dependencies
    ├── scripts/
    │   ├── __init__.py
    │   ├── api.py                  # GoCardless API client
    │   ├── auth.py                 # Token management
    │   ├── sync.py                 # Transaction sync
    │   ├── categorize.py           # Auto-categorization
    │   ├── charts.py               # Chart generation
    │   ├── reports.py              # Report generation
    │   └── commands.py             # CLI entry points
    ├── data/
    │   ├── categories.json         # Category definitions + rules
    │   └── merchants.json          # Known merchant mappings
    └── templates/
        ├── daily.md                # Daily report template
        ├── weekly.md               # Weekly report template
        └── monthly.md              # Monthly report template
```

**Runtime data location:** `~/.config/clawdbot-finance/`
```
~/.config/clawdbot-finance/
├── transactions.db                 # SQLite database
├── reports/                        # Generated report archives
│   └── 2026-01/
│       ├── daily-2026-01-29.md
│       └── weekly-2026-W04.md
├── state.json                      # Sync state, last run times
└── user_categories.json            # User overrides
```

---

## 4. Script Specifications

### 4.1 `auth.py` — Token Management

**Purpose:** Manage GoCardless API authentication tokens

**Functions:**
```python
def get_user_secrets() -> tuple[str, str]:
    """Retrieve secret_id and secret_key from Keychain."""
    
def get_refresh_token() -> str:
    """Get refresh token from Keychain, create new if expired."""
    
def get_access_token() -> str:
    """Get valid access token, refresh if needed."""
    
def store_refresh_token(token: str, expires: int) -> None:
    """Store refresh token in Keychain."""
    
def is_token_expired(token_key: str) -> bool:
    """Check if stored token is expired."""
```

**Keychain keys:**
- `gocardless_secret_id`
- `gocardless_secret_key`
- `gocardless_refresh_token`
- `gocardless_refresh_expires` (timestamp)
- `gocardless_access_token`
- `gocardless_access_expires` (timestamp)

**Complexity:** Medium (3-4 hours)

---

### 4.2 `api.py` — GoCardless API Client

**Purpose:** Wrap GoCardless Bank Account Data API

**Class:**
```python
class GoCardlessClient:
    BASE_URL = "https://bankaccountdata.gocardless.com/api/v2"
    
    def __init__(self):
        self.access_token = get_access_token()
    
    def list_institutions(self, country: str) -> list[dict]:
        """GET /institutions/?country={cc}"""
        
    def create_agreement(self, institution_id: str, 
                         max_historical_days: int = 90,
                         access_valid_for_days: int = 90) -> dict:
        """POST /agreements/enduser/"""
        
    def create_requisition(self, institution_id: str, 
                           redirect_url: str,
                           agreement_id: str = None) -> dict:
        """POST /requisitions/"""
        
    def get_requisition(self, requisition_id: str) -> dict:
        """GET /requisitions/{id}/"""
        
    def get_account_details(self, account_id: str) -> dict:
        """GET /accounts/{id}/details/"""
        
    def get_account_balances(self, account_id: str) -> dict:
        """GET /accounts/{id}/balances/"""
        
    def get_account_transactions(self, account_id: str,
                                  date_from: str = None,
                                  date_to: str = None) -> dict:
        """GET /accounts/{id}/transactions/"""
```

**Error handling:**
- Rate limit detection (429) with backoff
- Token refresh on 401
- Network timeout handling

**Complexity:** Medium (4-5 hours)

---

### 4.3 `sync.py` — Transaction Sync

**Purpose:** Fetch transactions from all connected accounts, store in SQLite

**Functions:**
```python
def sync_all_accounts(force: bool = False) -> SyncResult:
    """Sync transactions for all connected accounts."""
    
def sync_account(account_id: str) -> int:
    """Sync single account, return count of new transactions."""
    
def get_connected_accounts() -> list[Account]:
    """List all accounts from stored requisitions."""
    
def should_sync(account_id: str) -> bool:
    """Check rate limits and last sync time."""
```

**CLI:**
```bash
python -m personal_finance.sync          # Sync all accounts
python -m personal_finance.sync --force  # Ignore rate limit checks
python -m personal_finance.sync --account <id>  # Sync specific account
```

**Output:**
```
Syncing 2 accounts...
✓ UBS Main (CH12...) — 23 new transactions
✓ Revolut (LT12...) — 7 new transactions
Sync complete: 30 new transactions
```

**Complexity:** Medium (3-4 hours)

---

### 4.4 `categorize.py` — Transaction Categorization

**Purpose:** Auto-categorize transactions using rule-based matching

**Strategy (in order):**
1. User overrides (exact transaction_id match)
2. Merchant database (exact `creditorName` match)
3. Pattern rules (regex on `creditorName` or `remittanceInformationUnstructured`)
4. MCC code mapping (if available)
5. Fallback to "Other"

**Functions:**
```python
def categorize_transaction(txn: Transaction) -> str:
    """Return category name for transaction."""
    
def categorize_batch(transactions: list[Transaction]) -> dict[str, str]:
    """Categorize multiple transactions, return {txn_id: category}."""
    
def add_merchant_rule(merchant_pattern: str, category: str) -> None:
    """Add/update merchant categorization rule."""
    
def set_transaction_category(txn_id: str, category: str) -> None:
    """Override category for specific transaction."""
```

**categories.json structure:**
```json
{
  "categories": [
    {"name": "groceries", "emoji": "🛒", "keywords": ["migros", "coop", "aldi", "lidl", "denner"]},
    {"name": "dining", "emoji": "🍽️", "keywords": ["restaurant", "cafe", "starbucks", "mcdonald"]},
    {"name": "transport", "emoji": "🚃", "keywords": ["sbb", "zvv", "uber", "taxi", "parking"]},
    {"name": "subscriptions", "emoji": "📺", "keywords": ["netflix", "spotify", "apple", "google"]}
  ],
  "patterns": [
    {"pattern": "^TWINT.*", "category": "transfers"},
    {"pattern": "KARTENZAHLUNG\\s+TANKSTELLE", "category": "transport"}
  ]
}
```

**Complexity:** Medium (3-4 hours)

---

### 4.5 `charts.py` — Chart Generation

**Purpose:** Generate mobile-optimized PNG charts

**Functions:**
```python
def spending_pie_chart(data: dict[str, float], title: str = None) -> BytesIO:
    """Create pie chart of spending by category."""
    
def daily_bar_chart(data: list[tuple[date, float]], title: str = None) -> BytesIO:
    """Create bar chart of daily spending."""
    
def category_comparison_chart(current: dict, previous: dict, title: str = None) -> BytesIO:
    """Create side-by-side bar comparison."""
    
def trend_line_chart(data: list[tuple[date, float]], title: str = None) -> BytesIO:
    """Create line chart showing spending trend."""
    
def budget_progress_chart(budgets: list[BudgetStatus]) -> BytesIO:
    """Create horizontal progress bars for budget tracking."""
```

**Code example — Pie chart:**
```python
import matplotlib.pyplot as plt
from io import BytesIO

def spending_pie_chart(data: dict[str, float], title: str = "Spending by Category") -> BytesIO:
    """
    Create mobile-optimized pie chart.
    
    Args:
        data: {category_name: amount} dict
        title: Chart title
        
    Returns:
        BytesIO with PNG data
    """
    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    
    # Sort by value, group small slices into "Other"
    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
    total = sum(data.values())
    
    labels, sizes, colors = [], [], []
    other = 0
    
    for cat, amount in sorted_data:
        if amount / total < 0.03:  # Less than 3%
            other += amount
        else:
            labels.append(f"{cat.title()}\n{amount:,.0f}")
            sizes.append(amount)
            colors.append(CATEGORY_COLORS.get(cat, '#95a5a6'))
    
    if other > 0:
        labels.append(f"Other\n{other:,.0f}")
        sizes.append(other)
        colors.append('#95a5a6')
    
    wedges, texts, autotexts = ax.pie(
        sizes, 
        labels=labels,
        colors=colors,
        autopct='%1.0f%%',
        pctdistance=0.75,
        startangle=90,
        textprops={'fontsize': 10}
    )
    
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf
```

**Complexity:** Medium-High (5-6 hours)

---

### 4.6 `reports.py` — Report Generation

**Purpose:** Generate formatted text reports and coordinate chart generation

**Functions:**
```python
def generate_daily_report(date: date = None) -> Report:
    """Generate daily brief with balance and yesterday's transactions."""
    
def generate_weekly_report(week: int = None, year: int = None) -> Report:
    """Generate weekly summary with category breakdown."""
    
def generate_monthly_report(month: int = None, year: int = None) -> Report:
    """Generate monthly deep-dive with comparisons."""
    
def format_report_text(report: Report) -> str:
    """Format report data as markdown/text for messaging."""
```

**Report dataclass:**
```python
@dataclass
class Report:
    type: str  # daily, weekly, monthly
    period_start: date
    period_end: date
    text: str
    charts: list[BytesIO]
    metadata: dict
```

**Template example (daily.md):**
```markdown
🌅 **Daily Finance Brief** — {{ date | format_date }}

💰 **Balances**
{% for account in accounts %}
• {{ account.name }}: {{ account.balance | currency }}
{% endfor %}

📊 **Yesterday** ({{ yesterday | format_date }})
Spent: **{{ total_spent | currency }}** ({{ transaction_count }} transactions)
{% for txn in transactions %}
• {{ txn.merchant | truncate(15) }}  {{ txn.amount | currency }}  {{ txn.category_emoji }}
{% endfor %}

{% if comparison %}
📈 vs. typical {{ weekday }}: {{ comparison.diff | currency_diff }} ({{ comparison.status }})
{% endif %}
```

**Complexity:** Medium (4-5 hours)

---

### 4.7 `commands.py` — CLI Entry Points

**Purpose:** Handle Telegram commands and CLI invocation

**Commands:**
```python
@command("/finance setup")
def cmd_setup(args: list[str]) -> Response:
    """Start bank connection flow."""
    
@command("/finance balance")
def cmd_balance() -> Response:
    """Show current balances."""
    
@command("/finance spending")
def cmd_spending(period: str = "today") -> Response:
    """Show spending summary."""
    
@command("/finance report")
def cmd_report(report_type: str = "daily") -> Response:
    """Generate and send report."""
    
@command("/finance sync")
def cmd_sync() -> Response:
    """Force transaction sync."""
    
@command("/finance budget set")
def cmd_budget_set(category: str, amount: float) -> Response:
    """Set budget for category."""
```

**CLI usage:**
```bash
# Via Python module
python -m personal_finance.commands setup
python -m personal_finance.commands report daily

# Via Clawdbot skill invocation
clawdbot skill personal-finance setup
```

**Complexity:** Medium (3-4 hours)

---

## 5. Database Schema

### 5.1 SQLite Tables

```sql
-- Connected bank accounts
CREATE TABLE accounts (
    id TEXT PRIMARY KEY,              -- GoCardless account ID
    requisition_id TEXT NOT NULL,     -- Parent requisition
    institution_id TEXT NOT NULL,     -- Bank identifier
    institution_name TEXT,            -- Human-readable bank name
    iban TEXT,                        -- Account IBAN
    name TEXT,                        -- Account nickname
    currency TEXT DEFAULT 'CHF',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TEXT,
    access_expires_at TEXT            -- When re-auth needed
);

-- Transactions
CREATE TABLE transactions (
    id TEXT PRIMARY KEY,              -- Our internal ID (hash of key fields)
    external_id TEXT,                 -- Bank's transaction ID
    account_id TEXT NOT NULL,
    booking_date TEXT NOT NULL,       -- YYYY-MM-DD
    value_date TEXT,
    amount REAL NOT NULL,             -- Negative = expense
    currency TEXT NOT NULL,
    creditor_name TEXT,               -- Who received money
    debtor_name TEXT,                 -- Who sent money
    description TEXT,                 -- remittanceInformationUnstructured
    mcc_code TEXT,                    -- Merchant category code
    category TEXT,                    -- Our assigned category
    category_source TEXT,             -- 'auto', 'user', 'rule'
    raw_data TEXT,                    -- Full JSON for debugging
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- Balances (latest only, updated on sync)
CREATE TABLE balances (
    account_id TEXT PRIMARY KEY,
    balance_type TEXT,                -- 'interimAvailable', 'closingBooked', etc.
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- User-defined budgets
CREATE TABLE budgets (
    category TEXT PRIMARY KEY,
    monthly_limit REAL NOT NULL,
    currency TEXT DEFAULT 'CHF',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);

-- Requisitions (bank connections)
CREATE TABLE requisitions (
    id TEXT PRIMARY KEY,              -- GoCardless requisition ID
    institution_id TEXT NOT NULL,
    status TEXT,                      -- 'CR', 'LN', 'EX', etc.
    agreement_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT
);

-- Sync state
CREATE TABLE sync_state (
    account_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,           -- 'transactions', 'balances', 'details'
    last_sync_at TEXT,
    last_success_at TEXT,
    rate_limit_reset TEXT,            -- When rate limit resets
    PRIMARY KEY (account_id, endpoint)
);

-- Indexes for common queries
CREATE INDEX idx_transactions_date ON transactions(booking_date);
CREATE INDEX idx_transactions_account ON transactions(account_id);
CREATE INDEX idx_transactions_category ON transactions(category);
```

### 5.2 Query Examples

```python
# Get spending by category for current month
def get_monthly_spending_by_category(year: int, month: int) -> dict[str, float]:
    query = """
        SELECT category, SUM(ABS(amount)) as total
        FROM transactions
        WHERE amount < 0
          AND strftime('%Y', booking_date) = ?
          AND strftime('%m', booking_date) = ?
        GROUP BY category
        ORDER BY total DESC
    """
    # ...

# Get daily spending for week
def get_daily_spending(start_date: date, end_date: date) -> list[tuple[date, float]]:
    query = """
        SELECT booking_date, SUM(ABS(amount)) as total
        FROM transactions
        WHERE amount < 0
          AND booking_date BETWEEN ? AND ?
        GROUP BY booking_date
        ORDER BY booking_date
    """
    # ...
```

**Complexity:** Low-Medium (2-3 hours)

---

## 6. Cron Job Setup

### 6.1 Scheduled Tasks

| Task | Schedule | Cron Expression | Model |
|------|----------|-----------------|-------|
| Transaction sync | Every 6 hours | `0 */6 * * *` | — (script) |
| Daily report | 8:00 AM | `0 8 * * *` | Sonnet |
| Weekly report | Sunday 6:00 PM | `0 18 * * 0` | Sonnet |
| Monthly report | 1st of month, 9:00 AM | `0 9 1 * *` | Sonnet |
| Token refresh check | Daily at 3:00 AM | `0 3 * * *` | — (script) |
| Re-auth reminder | Weekly Monday 9:00 AM | `0 9 * * 1` | Sonnet |

### 6.2 Clawdbot Cron Configuration

```bash
# Add to Clawdbot cron
clawdbot cron add "finance-sync" "0 */6 * * *" \
  "python ~/.config/clawdbot/skills/personal-finance/scripts/sync.py"

clawdbot cron add "finance-daily-report" "0 8 * * *" \
  --model sonnet \
  "Generate and send the daily finance report using /finance report daily"

clawdbot cron add "finance-weekly-report" "0 18 * * 0" \
  --model sonnet \
  "Generate and send the weekly finance summary using /finance report weekly"

clawdbot cron add "finance-monthly-report" "0 9 1 * *" \
  --model sonnet \
  "Generate and send the monthly finance deep-dive using /finance report monthly"
```

### 6.3 Report Delivery

Reports are sent via the Clawdbot `message` tool:
```python
# In reports.py
def send_report(report: Report, channel: str = "telegram"):
    # Send text
    message.send(target=USER_TELEGRAM_ID, message=report.text)
    
    # Send each chart as image
    for chart in report.charts:
        message.send(target=USER_TELEGRAM_ID, buffer=chart, contentType="image/png")
```

**Complexity:** Low (1-2 hours)

---

## 7. Security Considerations

### 7.1 Credential Storage

| Secret | Storage | Key Name |
|--------|---------|----------|
| GoCardless secret_id | Keychain | `gocardless_secret_id` |
| GoCardless secret_key | Keychain | `gocardless_secret_key` |
| Refresh token | Keychain | `gocardless_refresh_token` |
| Access token | Keychain or memory | `gocardless_access_token` |

**Never store in:**
- Plain text files
- Environment variables (except for testing)
- Git history
- Logs

### 7.2 Data Protection

1. **SQLite database** — Store in `~/.config/clawdbot-finance/` with restrictive permissions (`chmod 700`)
2. **Transaction data** — Contains sensitive financial info; never log full transaction details
3. **Charts** — Generate in memory (BytesIO), delete after sending
4. **Reports** — Archive to local disk only, not cloud
5. **API calls** — Always use HTTPS, validate certificates

### 7.3 Bank Access Scope

- **Read-only**: Only request `balances`, `details`, `transactions` scopes
- **No PIS**: Do not request payment initiation permissions
- **Minimal history**: Request only necessary historical days (90 default)

### 7.4 Re-authentication Handling

Bank access expires after 90 days. The skill should:
1. Track expiry date in database
2. Send reminder 7 days before expiry
3. Provide easy re-auth flow via `/finance reconnect`

---

## 8. SKILL.md Template

```markdown
---
name: personal-finance
description: Personal finance tracking via GoCardless Open Banking. Syncs transactions, auto-categorizes spending, generates charts and reports.
homepage: https://developer.gocardless.com/bank-account-data/
metadata: 
  clawdbot:
    emoji: 💰
    os: [darwin]
    requires:
      env: [GOCARDLESS_SECRET_ID]
    commands:
      - /finance
---

# 💰 Personal Finance

Track your spending, generate reports, and get insights from your bank accounts.

## Setup

1. Create a GoCardless Bank Account Data account at https://bankaccountdata.gocardless.com
2. Get your user secrets from https://bankaccountdata.gocardless.com/user-secrets/
3. Store credentials:
   ```bash
   python ~/.config/clawdbot/skills/personal-finance/scripts/auth.py setup
   # Follow prompts to enter secret_id and secret_key
   ```
4. Connect your bank:
   ```
   /finance setup
   ```

## Commands

| Command | Description |
|---------|-------------|
| `/finance setup` | Connect a new bank account |
| `/finance balance` | Show current account balances |
| `/finance spending [today\|week\|month]` | Show spending summary |
| `/finance report [daily\|weekly\|monthly]` | Generate detailed report |
| `/finance compare [month1] [month2]` | Compare two months |
| `/finance budget set <category> <amount>` | Set monthly budget |
| `/finance budget` | Show budget progress |
| `/finance categorize <txn_id> <category>` | Override transaction category |
| `/finance accounts` | List connected accounts |
| `/finance sync` | Force transaction sync |
| `/finance reconnect` | Re-authenticate expiring connection |

## Scheduled Reports

Reports are automatically sent:
- **Daily brief**: 8:00 AM — balances + yesterday's spending
- **Weekly summary**: Sunday 6:00 PM — category breakdown + trends
- **Monthly deep-dive**: 1st of month 9:00 AM — full analysis + comparisons

## Categories

Default categories: Groceries 🛒, Dining 🍽️, Transport 🚃, Shopping 🛍️, Subscriptions 📺, Utilities ⚡, Entertainment 🎮, Health 🏥, Housing 🏠, Other

Override with `/finance categorize <transaction_id> <category>`

## Supported Banks

2,300+ European banks via PSD2 Open Banking. Check availability at:
https://docs.google.com/spreadsheets/d/1EZ5n7QDGaRIot5M86dwqd5UFSGEDTeTRzEq3D9uEDkM/

## Data Storage

- Transactions: `~/.config/clawdbot-finance/transactions.db` (SQLite)
- Reports: `~/.config/clawdbot-finance/reports/`
- All credentials in macOS Keychain (never plain text)
```

---

## 9. Implementation Order

### Phase 1: Foundation (Days 1-2)
| Step | Task | Complexity | Est. Hours |
|------|------|------------|------------|
| 1.1 | Create skill directory structure | Low | 0.5 |
| 1.2 | Implement `auth.py` — Keychain integration | Medium | 3 |
| 1.3 | Implement `api.py` — GoCardless client | Medium | 4 |
| 1.4 | Create SQLite schema + migrations | Low | 2 |
| 1.5 | Test with GoCardless sandbox | Low | 1 |

### Phase 2: Data Pipeline (Days 3-4)
| Step | Task | Complexity | Est. Hours |
|------|------|------------|------------|
| 2.1 | Implement `sync.py` — transaction fetching | Medium | 3 |
| 2.2 | Implement `categorize.py` — rule engine | Medium | 4 |
| 2.3 | Create `categories.json` with Swiss merchants | Low | 2 |
| 2.4 | Test full sync flow with real bank | Medium | 2 |

### Phase 3: Visualization (Days 5-6)
| Step | Task | Complexity | Est. Hours |
|------|------|------------|------------|
| 3.1 | Implement `charts.py` — pie chart | Medium | 2 |
| 3.2 | Implement bar charts (daily/comparison) | Medium | 2 |
| 3.3 | Implement trend line chart | Medium | 1.5 |
| 3.4 | Implement budget progress bars | Low | 1 |
| 3.5 | Test chart rendering on mobile Telegram | Low | 1 |

### Phase 4: Reports (Days 7-8)
| Step | Task | Complexity | Est. Hours |
|------|------|------------|------------|
| 4.1 | Implement `reports.py` — daily report | Medium | 2 |
| 4.2 | Implement weekly report | Medium | 2 |
| 4.3 | Implement monthly report | Medium | 3 |
| 4.4 | Create report templates | Low | 1 |
| 4.5 | Test report delivery via Telegram | Low | 1 |

### Phase 5: Commands & Automation (Days 9-10)
| Step | Task | Complexity | Est. Hours |
|------|------|------------|------------|
| 5.1 | Implement `commands.py` — all commands | Medium | 4 |
| 5.2 | Setup cron jobs | Low | 1 |
| 5.3 | Write SKILL.md documentation | Low | 1 |
| 5.4 | End-to-end testing | Medium | 3 |
| 5.5 | Bug fixes and polish | Medium | 2 |

### Total Estimated Effort
| Phase | Hours |
|-------|-------|
| Phase 1: Foundation | 10.5 |
| Phase 2: Data Pipeline | 11 |
| Phase 3: Visualization | 7.5 |
| Phase 4: Reports | 9 |
| Phase 5: Commands | 11 |
| **Total** | **49 hours** |

**Realistic timeline:** 2-3 weeks at part-time, 1-2 weeks full-time

---

## 10. Dependencies

### Python Packages (pyproject.toml)

```toml
[project]
name = "clawdbot-personal-finance"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.31.0",
    "matplotlib>=3.8.0",
    "jinja2>=3.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
]

[project.scripts]
finance-sync = "personal_finance.sync:main"
finance-report = "personal_finance.reports:main"
```

### System Dependencies

- Python 3.10+
- SQLite3 (built into Python)
- macOS Keychain (via `keychain.py` helper in Clawdbot)

---

## 11. Open Questions & Decisions

### Resolved
1. **GoCardless free tier limits?** — Unlimited connections, "non-verified" badge only
2. **Token storage approach?** — macOS Keychain via existing `keychain.py` helper

### To Decide During Implementation
1. **Multi-currency support?** — Start with single currency (CHF), add conversion later
2. **Historical data import?** — Support one-time import from CSV/spreadsheet?
3. **Notification preferences?** — Allow users to customize report times?
4. **Budget rollover?** — Should unused budget roll to next month?

### Technical Risks
1. **Bank-specific quirks** — Transaction formats vary; need extensive testing
2. **Rate limit handling** — Some banks limit to 4 calls/day; sync strategy critical
3. **Re-auth UX** — 90-day expiry requires smooth reconnection flow
4. **Categorization accuracy** — May need ML fallback if rule-based < 80%

---

## 12. Testing Strategy

### Unit Tests
- `test_auth.py` — Token refresh logic, expiry handling
- `test_categorize.py` — Rule matching, pattern edge cases
- `test_charts.py` — Chart generation, output format validation

### Integration Tests
- GoCardless sandbox (institution: `SANDBOXFINANCE_SFIN0000`)
- Full sync → categorize → report pipeline
- Telegram message delivery

### Manual Testing Checklist
- [ ] Bank connection flow (OAuth redirect)
- [ ] Transaction sync with real bank
- [ ] Chart rendering on mobile Telegram
- [ ] All report types generate correctly
- [ ] Commands respond appropriately
- [ ] Cron jobs trigger on schedule
- [ ] Re-auth flow works smoothly
- [ ] Budget tracking calculations correct

---

## Appendix A: GoCardless Sandbox Testing

Use the sandbox institution for development:

```python
# Institution ID for sandbox
SANDBOX_INSTITUTION = "SANDBOXFINANCE_SFIN0000"

# Test credentials (provided by GoCardless sandbox)
# User: any string
# Password: any string
# OTP: any 6 digits
```

Sandbox provides realistic test data including:
- Multiple accounts (current + savings)
- Transaction history
- Balance information

---

## Appendix B: Swiss Bank Institution IDs

Common Swiss banks for testing:

| Bank | Institution ID |
|------|----------------|
| UBS | `UBS_UBSWCHZH80A` |
| Credit Suisse | `CREDIT_SUISSE_CRESCHZZ80A` |
| Raiffeisen | `RAIFFEISEN_RAABORSCHB` |
| PostFinance | `POSTFINANCE_POFICHBEXXX` |
| ZKB | `ZKB_ZKBKCHZZ80A` |
| Revolut | `REVOLUT_REVOGB21` |

Note: Availability depends on PSD2 compliance; verify via institutions endpoint.
