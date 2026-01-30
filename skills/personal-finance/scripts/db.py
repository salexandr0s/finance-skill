#!/usr/bin/env python3
"""
Database operations for finance skill
Handles SQLite storage of accounts, transactions, budgets
"""

import os
import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from contextlib import contextmanager

try:
    from config import DAILY_API_CALL_LIMIT, DB_FILE_PERMISSIONS
except ImportError:
    DAILY_API_CALL_LIMIT = 3
    DB_FILE_PERMISSIONS = 0o600

# Database location
DB_PATH = Path.home() / '.config' / 'clawdbot-finance' / 'transactions.db'

def ensure_db_dir():
    """Ensure database directory exists"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

@contextmanager
def get_db():
    """Get database connection with context manager"""
    ensure_db_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    """Initialize database with schema"""
    with get_db() as conn:
        # Connected bank accounts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                requisition_id TEXT NOT NULL,
                institution_id TEXT NOT NULL,
                institution_name TEXT,
                iban TEXT,
                name TEXT,
                currency TEXT DEFAULT 'CHF',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_sync_at TEXT,
                last_import_at TEXT,
                access_expires_at TEXT
            )
        """)
        
        # Transactions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                external_id TEXT,
                account_id TEXT NOT NULL,
                booking_date TEXT NOT NULL,
                value_date TEXT,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                creditor_name TEXT,
                debtor_name TEXT,
                description TEXT,
                mcc_code TEXT,
                category TEXT,
                category_source TEXT DEFAULT 'auto',
                raw_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        
        # Balances (latest only)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS balances (
                account_id TEXT PRIMARY KEY,
                balance_type TEXT,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        
        # User budgets
        conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                category TEXT PRIMARY KEY,
                monthly_limit REAL NOT NULL,
                currency TEXT DEFAULT 'CHF',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            )
        """)
        
        # Requisitions (bank connections - legacy GoCardless)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS requisitions (
                id TEXT PRIMARY KEY,
                institution_id TEXT NOT NULL,
                institution_name TEXT,
                status TEXT,
                agreement_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT
            )
        """)

        # Sessions (Enable Banking connections)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                institution_name TEXT,
                status TEXT DEFAULT 'active',
                valid_until TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Rate limiting state
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                account_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                last_call_at TEXT,
                calls_today INTEGER DEFAULT 0,
                reset_date TEXT,
                PRIMARY KEY (account_id, endpoint)
            )
        """)

        # User settings (including home currency preference)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Exchange rates cache
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rates (
                base_currency TEXT NOT NULL,
                target_currency TEXT NOT NULL,
                rate REAL NOT NULL,
                rate_date TEXT NOT NULL,
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (base_currency, target_currency, rate_date)
            )
        """)

        # Crypto wallets
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                id TEXT PRIMARY KEY,
                address TEXT NOT NULL,
                blockchain TEXT NOT NULL,
                label TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(address, blockchain)
            )
        """)

        # Wallet snapshots (for historical tracking)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wallet_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_id TEXT NOT NULL,
                total_value_usd REAL NOT NULL,
                positions_json TEXT,
                snapshot_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (wallet_id) REFERENCES wallets(id)
            )
        """)

        # Subscriptions (recurring payments)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'EUR',
                billing_cycle TEXT NOT NULL DEFAULT 'monthly'
                    CHECK (billing_cycle IN ('weekly', 'monthly', 'quarterly', 'yearly')),
                next_billing_date TEXT,
                last_billing_date TEXT,
                category TEXT DEFAULT 'subscriptions',
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'paused', 'cancelled')),
                merchant_pattern TEXT,
                notes TEXT,
                website TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(booking_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_amount ON transactions(amount)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_snapshots_date ON wallet_snapshots(wallet_id, snapshot_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_next_billing ON subscriptions(next_billing_date)")

        conn.commit()

    # Set restrictive permissions on database file (owner read/write only)
    if DB_PATH.exists():
        os.chmod(DB_PATH, DB_FILE_PERMISSIONS)

def store_requisition(requisition_data: Dict, institution_data: Dict):
    """Store requisition info (legacy GoCardless)"""
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO requisitions
            (id, institution_id, institution_name, status, agreement_id, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            requisition_data['id'],
            institution_data['id'],
            institution_data['name'],
            requisition_data['status'],
            requisition_data.get('agreement'),
            None  # Will be updated when we know expiry
        ))
        conn.commit()

def get_pending_requisitions() -> List[Dict]:
    """Get requisitions waiting for user to complete auth (legacy GoCardless)"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT * FROM requisitions
            WHERE status IN ('CR', 'GC')
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# Enable Banking Session Functions
# =============================================================================

def store_session(session_data: Dict) -> None:
    """
    Store Enable Banking session info.

    Args:
        session_data: Session response from Enable Banking API containing
                     session_id, accounts, and optional validity info
    """
    with get_db() as conn:
        session_id = session_data.get('session_id')
        if not session_id:
            return

        # Extract validity if present
        valid_until = session_data.get('access', {}).get('valid_until')

        conn.execute("""
            INSERT OR REPLACE INTO sessions
            (session_id, status, valid_until)
            VALUES (?, 'active', ?)
        """, (session_id, valid_until))
        conn.commit()


def get_active_sessions() -> List[Dict]:
    """
    Get all active Enable Banking sessions.

    Returns:
        List of session dictionaries that are still valid
    """
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT * FROM sessions
            WHERE status = 'active'
            AND (valid_until IS NULL OR valid_until > datetime('now'))
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def store_accounts(session_id: str, account_data: Dict) -> None:
    """
    Store account info from Enable Banking session.

    Args:
        session_id: Enable Banking session ID
        account_data: Account object from Enable Banking API
    """
    with get_db() as conn:
        # Handle Enable Banking account format
        account_uid = account_data.get('uid') or account_data.get('id')
        if not account_uid:
            return

        # Extract account details - Enable Banking format
        iban = account_data.get('iban', '')
        currency = account_data.get('currency', 'EUR')
        name = account_data.get('name', '')
        institution_name = account_data.get('institution_name', '')

        conn.execute("""
            INSERT OR REPLACE INTO accounts
            (id, requisition_id, institution_id, institution_name, iban, name, currency, access_expires_at)
            VALUES (?, ?, '', ?, ?, ?, ?, ?)
        """, (
            account_uid,
            session_id,  # Use session_id in requisition_id field for compatibility
            institution_name,
            iban,
            name,
            currency,
            datetime.now() + timedelta(days=90)  # 90 day default
        ))
        conn.commit()


def store_accounts_legacy(requisition_id: str, account_id: str, details: Dict, institution_name: str):
    """Store account info"""
    with get_db() as conn:
        iban = details.get('account', {}).get('iban')
        currency = details.get('account', {}).get('currency', 'CHF')
        
        conn.execute("""
            INSERT OR REPLACE INTO accounts
            (id, requisition_id, institution_id, institution_name, iban, currency, access_expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            account_id,
            requisition_id,
            '', # Will be filled from requisition
            institution_name,
            iban,
            currency,
            datetime.now() + timedelta(days=90)  # 90 day default
        ))
        conn.commit()

def get_connected_accounts() -> List[Dict]:
    """Get all connected accounts"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT * FROM accounts 
            WHERE access_expires_at > datetime('now')
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

def store_transactions(account_id: str, transaction_data: Dict) -> int:
    """Store transactions, return count of new ones"""
    if not transaction_data or 'transactions' not in transaction_data:
        return 0
        
    transactions = transaction_data['transactions'].get('booked', [])
    new_count = 0
    
    with get_db() as conn:
        for txn in transactions:
            # Create deterministic ID
            txn_id = create_transaction_id(account_id, txn)
            
            # Check if already exists
            cursor = conn.execute("SELECT 1 FROM transactions WHERE id = ?", (txn_id,))
            if cursor.fetchone():
                continue  # Skip existing
                
            # Parse transaction
            amount = float(txn['transactionAmount']['amount'])
            currency = txn['transactionAmount']['currency']
            booking_date = txn['bookingDate']
            value_date = txn.get('valueDate', booking_date)
            
            creditor = txn.get('creditorName')
            debtor = txn.get('debtorName')
            description = txn.get('remittanceInformationUnstructured', '')
            
            # Store transaction
            conn.execute("""
                INSERT INTO transactions
                (id, external_id, account_id, booking_date, value_date, amount, currency,
                 creditor_name, debtor_name, description, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                txn_id,
                txn.get('transactionId'),
                account_id,
                booking_date,
                value_date,
                amount,
                currency,
                creditor,
                debtor,
                description,
                json.dumps(txn)
            ))
            new_count += 1
            
        # Update last sync time
        conn.execute("""
            UPDATE accounts 
            SET last_sync_at = datetime('now')
            WHERE id = ?
        """, (account_id,))
        
        conn.commit()
        
    return new_count

def create_transaction_id(account_id: str, transaction: Dict) -> str:
    """Create deterministic transaction ID"""
    # Use key fields to create unique hash
    key_data = f"{account_id}|{transaction['bookingDate']}|{transaction['transactionAmount']['amount']}|{transaction.get('creditorName', '')}|{transaction.get('transactionId', '')}"
    return hashlib.md5(key_data.encode()).hexdigest()

def get_account_balances() -> List[Dict]:
    """Get current account balances"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT a.name, a.iban, b.amount, b.currency
            FROM accounts a
            LEFT JOIN balances b ON a.id = b.account_id
            WHERE a.access_expires_at > datetime('now')
            ORDER BY a.institution_name, a.name
        """)
        return [dict(row) for row in cursor.fetchall()]

def store_balances(account_id: str, balance_data: Dict):
    """Store account balances"""
    if not balance_data or 'balances' not in balance_data:
        return
        
    balances = balance_data['balances']
    if not balances:
        return
        
    # Use the first available balance (prefer interimAvailable > closingBooked)
    balance_types = ['interimAvailable', 'closingBooked', 'expected']
    selected_balance = None
    
    for balance in balances:
        if balance['balanceType'] in balance_types:
            if not selected_balance or balance_types.index(balance['balanceType']) < balance_types.index(selected_balance['balanceType']):
                selected_balance = balance
                
    if not selected_balance:
        selected_balance = balances[0]  # Fallback to first
        
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO balances
            (account_id, balance_type, amount, currency, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (
            account_id,
            selected_balance['balanceType'],
            float(selected_balance['balanceAmount']['amount']),
            selected_balance['balanceAmount']['currency']
        ))
        conn.commit()

def get_category_spending(start_date: date, end_date: date) -> Dict[str, float]:
    """Get spending by category for date range"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT COALESCE(category, 'other') as category, SUM(ABS(amount)) as total
            FROM transactions
            WHERE amount < 0 
            AND booking_date >= ? 
            AND booking_date <= ?
            GROUP BY COALESCE(category, 'other')
            ORDER BY total DESC
        """, (start_date.isoformat(), end_date.isoformat()))
        
        return {row['category']: row['total'] for row in cursor.fetchall()}

def get_historical_category_averages(period: str, num_periods: int = 6) -> Dict[str, float]:
    """Get historical spending averages by category"""
    with get_db() as conn:
        if period == 'today':
            # Daily averages - look at same weekday over past weeks
            today = date.today()
            weekday = today.weekday()
            
            cursor = conn.execute("""
                SELECT COALESCE(category, 'other') as category, AVG(daily_total) as avg_amount
                FROM (
                    SELECT category, booking_date, SUM(ABS(amount)) as daily_total
                    FROM transactions 
                    WHERE amount < 0 
                    AND strftime('%w', booking_date) = ?
                    AND booking_date >= date('now', '-6 weeks')
                    AND booking_date < date('now')
                    GROUP BY category, booking_date
                )
                GROUP BY category
            """, (str((weekday + 1) % 7),))  # SQLite weekday starts at 0=Sunday
            
        elif period == 'week':
            # Weekly averages
            cursor = conn.execute("""
                SELECT COALESCE(category, 'other') as category, AVG(weekly_total) as avg_amount
                FROM (
                    SELECT category, strftime('%Y-W%W', booking_date) as week, SUM(ABS(amount)) as weekly_total
                    FROM transactions 
                    WHERE amount < 0 
                    AND booking_date >= date('now', '-6 months')
                    GROUP BY category, week
                )
                GROUP BY category
            """)
            
        elif period == 'month':
            # Monthly averages
            cursor = conn.execute("""
                SELECT COALESCE(category, 'other') as category, AVG(monthly_total) as avg_amount
                FROM (
                    SELECT category, strftime('%Y-%m', booking_date) as month, SUM(ABS(amount)) as monthly_total
                    FROM transactions 
                    WHERE amount < 0 
                    AND booking_date >= date('now', '-2 years')
                    GROUP BY category, month
                )
                GROUP BY category
            """)
        else:
            return {}
            
        return {row['category']: row['avg_amount'] for row in cursor.fetchall()}

def set_category_budget(category: str, amount: float) -> bool:
    """Set monthly budget for category"""
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO budgets
                (category, monthly_limit, updated_at)
                VALUES (?, ?, datetime('now'))
            """, (category, amount))
            conn.commit()
            return True
    except Exception:
        return False

def get_budget_status(start_date: date, end_date: date) -> List[Dict]:
    """Get budget vs actual spending"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT 
                b.category,
                b.monthly_limit,
                COALESCE(SUM(ABS(t.amount)), 0) as spent
            FROM budgets b
            LEFT JOIN transactions t ON b.category = t.category 
                AND t.amount < 0
                AND t.booking_date >= ?
                AND t.booking_date <= ?
            GROUP BY b.category, b.monthly_limit
            ORDER BY spent DESC
        """, (start_date.isoformat(), end_date.isoformat()))
        
        return [dict(row) for row in cursor.fetchall()]

def set_transaction_category(transaction_id: str, category: str) -> bool:
    """Override transaction category"""
    try:
        with get_db() as conn:
            cursor = conn.execute("""
                UPDATE transactions 
                SET category = ?, category_source = 'user'
                WHERE id LIKE ?
            """, (category, f"{transaction_id}%"))
            
            if cursor.rowcount > 0:
                conn.commit()
                return True
            return False
    except Exception:
        return False

def check_rate_limit(account_id: str, endpoint: str = 'transactions') -> bool:
    """Check if we can make API call without hitting rate limit"""
    today = date.today().isoformat()
    
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT calls_today, reset_date FROM rate_limits
            WHERE account_id = ? AND endpoint = ?
        """, (account_id, endpoint))
        
        row = cursor.fetchone()
        if not row:
            # First call, allow it
            return True
            
        # Reset counter if new day
        if row['reset_date'] != today:
            conn.execute("""
                UPDATE rate_limits
                SET calls_today = 0, reset_date = ?, last_call_at = NULL
                WHERE account_id = ? AND endpoint = ?
            """, (today, account_id, endpoint))
            conn.commit()
            return True
            
        # Check if under limit
        return row['calls_today'] < DAILY_API_CALL_LIMIT

def record_api_call(account_id: str, endpoint: str = 'transactions'):
    """Record an API call for rate limiting"""
    today = date.today().isoformat()
    
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO rate_limits
            (account_id, endpoint, last_call_at, calls_today, reset_date)
            VALUES (?, ?, datetime('now'), 
                    COALESCE((SELECT calls_today FROM rate_limits WHERE account_id = ? AND endpoint = ?), 0) + 1, 
                    ?)
        """, (account_id, endpoint, account_id, endpoint, today))
        conn.commit()

def get_recent_transactions(days: int = 7) -> List[Dict]:
    """Get recent transactions for categorization"""
    # Validate input is a positive integer to prevent SQL injection
    if not isinstance(days, int) or days < 0:
        days = 7

    with get_db() as conn:
        cursor = conn.execute(f"""
            SELECT * FROM transactions
            WHERE booking_date >= date('now', '-{int(days)} days')
            AND category IS NULL
            ORDER BY booking_date DESC
        """)

        return [dict(row) for row in cursor.fetchall()]

def update_transaction_categories(category_updates: Dict[str, str]):
    """Bulk update transaction categories"""
    with get_db() as conn:
        for txn_id, category in category_updates.items():
            conn.execute("""
                UPDATE transactions
                SET category = ?, category_source = 'auto'
                WHERE id = ?
            """, (category, txn_id))
        conn.commit()

def get_spending_by_period(period: str, num_periods: int = 30) -> List[Tuple[str, float]]:
    """Get spending aggregated by time period"""
    # Validate input is a positive integer to prevent SQL injection
    if not isinstance(num_periods, int) or num_periods < 0:
        num_periods = 30

    with get_db() as conn:
        if period == 'day':
            cursor = conn.execute(f"""
                SELECT booking_date, SUM(ABS(amount)) as total
                FROM transactions
                WHERE amount < 0
                AND booking_date >= date('now', '-{int(num_periods)} days')
                GROUP BY booking_date
                ORDER BY booking_date
            """)
        elif period == 'week':
            cursor = conn.execute(f"""
                SELECT strftime('%Y-W%W', booking_date) as period, SUM(ABS(amount)) as total
                FROM transactions
                WHERE amount < 0
                AND booking_date >= date('now', '-{int(num_periods)} weeks')
                GROUP BY period
                ORDER BY period
            """)
        elif period == 'month':
            cursor = conn.execute(f"""
                SELECT strftime('%Y-%m', booking_date) as period, SUM(ABS(amount)) as total
                FROM transactions
                WHERE amount < 0
                AND booking_date >= date('now', '-{int(num_periods)} months')
                GROUP BY period
                ORDER BY period
            """)
        else:
            return []

        return [(row['booking_date'] if period == 'day' else row['period'], row['total'])
                for row in cursor.fetchall()]


# ============================================================================
# User Settings Functions
# ============================================================================

def get_user_setting(key: str, default: str = None) -> Optional[str]:
    """Get a user setting value"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT value FROM user_settings WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row['value'] if row else default


def set_user_setting(key: str, value: str) -> None:
    """Set a user setting value"""
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO user_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, value))
        conn.commit()


def get_home_currency() -> str:
    """Get user's preferred home currency"""
    try:
        from config import DEFAULT_HOME_CURRENCY
    except ImportError:
        DEFAULT_HOME_CURRENCY = "EUR"
    return get_user_setting('home_currency', DEFAULT_HOME_CURRENCY)


def set_home_currency(currency: str) -> None:
    """Set user's preferred home currency"""
    set_user_setting('home_currency', currency.upper())


# ============================================================================
# Exchange Rate Functions
# ============================================================================

def get_cached_rate(base: str, target: str, rate_date: str = None) -> Optional[float]:
    """Get cached exchange rate for a specific date"""
    if rate_date is None:
        rate_date = date.today().isoformat()

    with get_db() as conn:
        cursor = conn.execute("""
            SELECT rate FROM exchange_rates
            WHERE base_currency = ? AND target_currency = ? AND rate_date = ?
        """, (base.upper(), target.upper(), rate_date))
        row = cursor.fetchone()
        return row['rate'] if row else None


def get_latest_cached_rate(base: str, target: str) -> Optional[Tuple[float, str]]:
    """Get most recent cached exchange rate (any date)"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT rate, rate_date FROM exchange_rates
            WHERE base_currency = ? AND target_currency = ?
            ORDER BY rate_date DESC
            LIMIT 1
        """, (base.upper(), target.upper()))
        row = cursor.fetchone()
        return (row['rate'], row['rate_date']) if row else None


def cache_exchange_rate(base: str, target: str, rate: float, rate_date: str = None) -> None:
    """Cache an exchange rate"""
    if rate_date is None:
        rate_date = date.today().isoformat()

    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO exchange_rates
            (base_currency, target_currency, rate, rate_date, fetched_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (base.upper(), target.upper(), rate, rate_date))
        conn.commit()


def cache_exchange_rates_bulk(base: str, rates: Dict[str, float], rate_date: str = None) -> None:
    """Cache multiple exchange rates at once"""
    if rate_date is None:
        rate_date = date.today().isoformat()

    with get_db() as conn:
        for target, rate in rates.items():
            conn.execute("""
                INSERT OR REPLACE INTO exchange_rates
                (base_currency, target_currency, rate, rate_date, fetched_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (base.upper(), target.upper(), rate, rate_date))
        conn.commit()


def cleanup_old_rates(days_to_keep: int = 90) -> int:
    """Remove exchange rates older than specified days, return count deleted"""
    with get_db() as conn:
        cursor = conn.execute(f"""
            DELETE FROM exchange_rates
            WHERE rate_date < date('now', '-{int(days_to_keep)} days')
        """)
        conn.commit()
        return cursor.rowcount


# ============================================================================
# Crypto Wallet Functions
# ============================================================================

def add_wallet(address: str, blockchain: str, label: str = None) -> bool:
    """Add a crypto wallet address"""
    try:
        # Create deterministic ID from address and blockchain
        wallet_id = hashlib.md5(f"{address.lower()}|{blockchain.lower()}".encode()).hexdigest()

        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO wallets
                (id, address, blockchain, label, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (wallet_id, address, blockchain.lower(), label))
            conn.commit()
        return True
    except Exception:
        return False


def remove_wallet(address: str, blockchain: str = None) -> bool:
    """Remove a wallet by address (and optionally blockchain)"""
    try:
        with get_db() as conn:
            if blockchain:
                # Remove specific wallet
                wallet_id = hashlib.md5(f"{address.lower()}|{blockchain.lower()}".encode()).hexdigest()
                conn.execute("DELETE FROM wallet_snapshots WHERE wallet_id = ?", (wallet_id,))
                cursor = conn.execute("DELETE FROM wallets WHERE id = ?", (wallet_id,))
            else:
                # Remove all wallets with this address (any chain)
                cursor = conn.execute("SELECT id FROM wallets WHERE LOWER(address) = LOWER(?)", (address,))
                wallet_ids = [row['id'] for row in cursor.fetchall()]
                for wid in wallet_ids:
                    conn.execute("DELETE FROM wallet_snapshots WHERE wallet_id = ?", (wid,))
                cursor = conn.execute("DELETE FROM wallets WHERE LOWER(address) = LOWER(?)", (address,))

            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        return False


def get_wallets() -> List[Dict]:
    """Get all stored wallets"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT * FROM wallets
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_wallet_by_id(wallet_id: str) -> Optional[Dict]:
    """Get a wallet by its ID"""
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM wallets WHERE id = ?", (wallet_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_wallet_by_address(address: str, blockchain: str = None) -> Optional[Dict]:
    """Get a wallet by address (and optionally blockchain)"""
    with get_db() as conn:
        if blockchain:
            wallet_id = hashlib.md5(f"{address.lower()}|{blockchain.lower()}".encode()).hexdigest()
            cursor = conn.execute("SELECT * FROM wallets WHERE id = ?", (wallet_id,))
        else:
            cursor = conn.execute("SELECT * FROM wallets WHERE LOWER(address) = LOWER(?)", (address,))
        row = cursor.fetchone()
        return dict(row) if row else None


def save_wallet_snapshot(wallet_id: str, total_value_usd: float,
                         positions_json: str = None, snapshot_date: str = None) -> bool:
    """Save a wallet snapshot for historical tracking"""
    try:
        if snapshot_date is None:
            snapshot_date = date.today().isoformat()

        with get_db() as conn:
            # Check if snapshot already exists for this date
            cursor = conn.execute("""
                SELECT id FROM wallet_snapshots
                WHERE wallet_id = ? AND snapshot_date = ?
            """, (wallet_id, snapshot_date))

            if cursor.fetchone():
                # Update existing snapshot
                conn.execute("""
                    UPDATE wallet_snapshots
                    SET total_value_usd = ?, positions_json = ?, created_at = CURRENT_TIMESTAMP
                    WHERE wallet_id = ? AND snapshot_date = ?
                """, (total_value_usd, positions_json, wallet_id, snapshot_date))
            else:
                # Insert new snapshot
                conn.execute("""
                    INSERT INTO wallet_snapshots
                    (wallet_id, total_value_usd, positions_json, snapshot_date)
                    VALUES (?, ?, ?, ?)
                """, (wallet_id, total_value_usd, positions_json, snapshot_date))

            conn.commit()
        return True
    except Exception:
        return False


def get_latest_wallet_snapshot(wallet_id: str) -> Optional[Dict]:
    """Get the most recent snapshot for a wallet"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT * FROM wallet_snapshots
            WHERE wallet_id = ?
            ORDER BY snapshot_date DESC
            LIMIT 1
        """, (wallet_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_wallet_snapshots_for_period(start_date: date, end_date: date) -> List[Dict]:
    """Get all wallet snapshots within a date range"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT ws.*, w.address, w.blockchain, w.label
            FROM wallet_snapshots ws
            JOIN wallets w ON ws.wallet_id = w.id
            WHERE ws.snapshot_date >= ? AND ws.snapshot_date <= ?
            ORDER BY ws.snapshot_date DESC, w.label
        """, (start_date.isoformat(), end_date.isoformat()))
        return [dict(row) for row in cursor.fetchall()]


def get_total_crypto_value() -> float:
    """Get total value across all wallets (from latest snapshots)"""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT SUM(ws.total_value_usd) as total
            FROM wallets w
            LEFT JOIN (
                SELECT wallet_id, total_value_usd,
                       ROW_NUMBER() OVER (PARTITION BY wallet_id ORDER BY snapshot_date DESC) as rn
                FROM wallet_snapshots
            ) ws ON w.id = ws.wallet_id AND ws.rn = 1
        """)
        row = cursor.fetchone()
        return row['total'] if row and row['total'] else 0.0


# ============================================================================
# CSV Import Account Functions
# ============================================================================

def store_csv_account(account_id: str, name: str, currency: str = 'EUR') -> bool:
    """
    Store or update a CSV import account.

    Args:
        account_id: Unique identifier for the account
        name: Friendly name for the account
        currency: Account currency code

    Returns:
        True if successful
    """
    try:
        with get_db() as conn:
            # Check if account exists
            cursor = conn.execute(
                "SELECT id FROM accounts WHERE id = ?", (account_id,)
            )
            exists = cursor.fetchone() is not None

            if exists:
                # Update existing account
                conn.execute("""
                    UPDATE accounts
                    SET name = ?, currency = ?, last_import_at = datetime('now')
                    WHERE id = ?
                """, (name, currency, account_id))
            else:
                # Insert new account
                conn.execute("""
                    INSERT INTO accounts
                    (id, requisition_id, institution_id, institution_name, name, currency,
                     created_at, access_expires_at)
                    VALUES (?, 'csv', 'csv_import', 'CSV Import', ?, ?,
                            datetime('now'), datetime('now', '+100 years'))
                """, (account_id, name, currency))

            conn.commit()
            return True
    except Exception:
        return False


def get_csv_accounts() -> List[Dict]:
    """Get all CSV-imported accounts with stats."""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT
                a.id,
                a.name,
                a.currency,
                a.created_at,
                a.last_import_at,
                COUNT(t.id) as transaction_count,
                MIN(t.booking_date) as oldest_transaction,
                MAX(t.booking_date) as latest_transaction,
                SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) as total_spending,
                SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) as total_income
            FROM accounts a
            LEFT JOIN transactions t ON a.id = t.account_id
            WHERE a.institution_id = 'csv_import'
            GROUP BY a.id
            ORDER BY a.name
        """)
        return [dict(row) for row in cursor.fetchall()]


def delete_csv_account(account_id: str, delete_transactions: bool = True) -> bool:
    """
    Delete a CSV import account.

    Args:
        account_id: Account to delete
        delete_transactions: Also delete associated transactions

    Returns:
        True if successful
    """
    try:
        with get_db() as conn:
            if delete_transactions:
                conn.execute(
                    "DELETE FROM transactions WHERE account_id = ?",
                    (account_id,)
                )

            cursor = conn.execute(
                "DELETE FROM accounts WHERE id = ? AND institution_id = 'csv_import'",
                (account_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        return False


def get_account_transaction_count(account_id: str) -> int:
    """Get number of transactions for an account."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM transactions WHERE account_id = ?",
            (account_id,)
        )
        row = cursor.fetchone()
        return row['count'] if row else 0


def get_transactions_for_period(account_id: str, start_date: date, end_date: date) -> List[Dict]:
    """Get transactions for an account within a date range."""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT * FROM transactions
            WHERE account_id = ?
            AND booking_date >= ?
            AND booking_date <= ?
            ORDER BY booking_date DESC
        """, (account_id, start_date.isoformat(), end_date.isoformat()))
        return [dict(row) for row in cursor.fetchall()]


# ============================================================================
# Subscription Functions
# ============================================================================

def add_subscription(
    name: str,
    amount: float,
    currency: str = 'EUR',
    billing_cycle: str = 'monthly',
    category: str = 'subscriptions',
    next_billing_date: str = None,
    merchant_pattern: str = None,
    notes: str = None,
    website: str = None
) -> int:
    """
    Add a new subscription.

    Returns:
        Subscription ID if successful, -1 on error
    """
    try:
        with get_db() as conn:
            cursor = conn.execute("""
                INSERT INTO subscriptions
                (name, amount, currency, billing_cycle, category,
                 next_billing_date, merchant_pattern, notes, website)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, amount, currency, billing_cycle, category,
                  next_billing_date, merchant_pattern, notes, website))
            conn.commit()
            return cursor.lastrowid
    except Exception:
        return -1


def update_subscription(
    subscription_id: int,
    **kwargs
) -> bool:
    """
    Update a subscription's fields.

    Args:
        subscription_id: ID of subscription to update
        **kwargs: Fields to update (name, amount, currency, billing_cycle,
                  category, next_billing_date, status, notes, website)

    Returns:
        True if successful
    """
    allowed_fields = {'name', 'amount', 'currency', 'billing_cycle', 'category',
                      'next_billing_date', 'last_billing_date', 'status',
                      'merchant_pattern', 'notes', 'website'}

    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return False

    updates['updated_at'] = datetime.now().isoformat()

    set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [subscription_id]

    try:
        with get_db() as conn:
            cursor = conn.execute(
                f"UPDATE subscriptions SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        return False


def delete_subscription(subscription_id: int) -> bool:
    """Delete a subscription."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM subscriptions WHERE id = ?",
                (subscription_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        return False


def get_subscriptions(status: str = None, include_cancelled: bool = False) -> List[Dict]:
    """
    Get all subscriptions.

    Args:
        status: Filter by status (active, paused, cancelled)
        include_cancelled: Include cancelled subscriptions

    Returns:
        List of subscription dictionaries
    """
    with get_db() as conn:
        if status:
            cursor = conn.execute(
                "SELECT * FROM subscriptions WHERE status = ? ORDER BY amount DESC",
                (status,)
            )
        elif include_cancelled:
            cursor = conn.execute(
                "SELECT * FROM subscriptions ORDER BY status, amount DESC"
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM subscriptions WHERE status != 'cancelled' ORDER BY amount DESC"
            )
        return [dict(row) for row in cursor.fetchall()]


def get_subscription_by_id(subscription_id: int) -> Optional[Dict]:
    """Get a single subscription by ID."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM subscriptions WHERE id = ?",
            (subscription_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_subscription_by_merchant(merchant_pattern: str) -> Optional[Dict]:
    """Get subscription by merchant pattern (for auto-detection linking)."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM subscriptions WHERE merchant_pattern = ?",
            (merchant_pattern,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_subscription_totals() -> Dict:
    """
    Get subscription spending totals.

    Returns:
        Dictionary with monthly_total, yearly_total, count, by_category
    """
    with get_db() as conn:
        # Get active subscriptions
        cursor = conn.execute("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
        """)
        subscriptions = [dict(row) for row in cursor.fetchall()]

    if not subscriptions:
        return {
            'monthly_total': 0.0,
            'yearly_total': 0.0,
            'count': 0,
            'by_category': {},
            'currency': 'EUR'
        }

    monthly_total = 0.0
    by_category = {}

    for sub in subscriptions:
        # Convert to monthly amount
        amount = sub['amount']
        cycle = sub['billing_cycle']

        if cycle == 'yearly':
            monthly_amount = amount / 12
        elif cycle == 'quarterly':
            monthly_amount = amount / 3
        elif cycle == 'weekly':
            monthly_amount = amount * 4.33
        else:  # monthly
            monthly_amount = amount

        monthly_total += monthly_amount

        # Group by category
        cat = sub.get('category', 'other')
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(sub)

    return {
        'monthly_total': round(monthly_total, 2),
        'yearly_total': round(monthly_total * 12, 2),
        'count': len(subscriptions),
        'subscriptions': subscriptions,
        'by_category': by_category,
        'currency': subscriptions[0]['currency'] if subscriptions else 'EUR'
    }


def get_upcoming_renewals(days: int = 7) -> List[Dict]:
    """Get subscriptions renewing in the next N days."""
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    today = date.today().isoformat()

    with get_db() as conn:
        cursor = conn.execute("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
            AND next_billing_date IS NOT NULL
            AND next_billing_date >= ?
            AND next_billing_date <= ?
            ORDER BY next_billing_date
        """, (today, cutoff))
        return [dict(row) for row in cursor.fetchall()]


# Initialize database on import
init_database()