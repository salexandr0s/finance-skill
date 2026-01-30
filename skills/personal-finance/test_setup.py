#!/usr/bin/env python3
"""
Test script for personal finance skill setup
"""

import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent / 'scripts'
templates_dir = Path(__file__).parent / 'templates'
sys.path.insert(0, str(scripts_dir))
sys.path.insert(0, str(templates_dir))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        import db
        print("  Database module imported")
    except Exception as e:
        print(f"  Database module failed: {e}")
        return False

    try:
        import csv_import
        print("  CSV import module imported")
    except Exception as e:
        print(f"  CSV import module failed: {e}")
        return False

    try:
        import categorize
        print("  Categorization module imported")
    except Exception as e:
        print(f"  Categorization module failed: {e}")
        return False

    try:
        import charts
        print("  Charts module imported")
    except Exception as e:
        print(f"  Charts module failed: {e}")
        return False

    try:
        import reports
        print("  Reports module imported")
    except Exception as e:
        print(f"  Reports module failed: {e}")
        return False

    try:
        import finance
        print("  Main finance module imported")
    except Exception as e:
        print(f"  Finance module failed: {e}")
        return False

    print("[PASS] All modules imported")
    return True

def test_database():
    """Test database initialization"""
    print("\nTesting database...")

    try:
        from db import init_database, get_db

        # Initialize database
        init_database()
        print("  Database initialized")

        # Test connection
        with get_db() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

        expected_tables = {'accounts', 'transactions', 'balances', 'budgets', 'rate_limits', 'user_settings', 'subscriptions', 'wallets', 'wallet_snapshots'}
        if expected_tables.issubset(set(tables)):
            print("[PASS] All database tables created")
            return True
        else:
            missing = expected_tables - set(tables)
            print(f"[FAIL] Missing tables: {missing}")
            return False

    except Exception as e:
        print(f"[FAIL] Database test failed: {e}")
        return False

def test_csv_import():
    """Test CSV import functionality"""
    print("\nTesting CSV import...")

    try:
        from csv_import import (
            detect_bank_format, parse_amount, parse_date,
            create_transaction_hash, get_supported_banks, BANK_FORMATS
        )
        from datetime import date

        # Test bank format detection
        csv_content = "Date;Amount;Description\n01.01.2025;-50.00;Test transaction"
        bank_key, config = detect_bank_format(csv_content)
        if bank_key:
            print(f"  Bank format detection working (detected: {bank_key})")
        else:
            print("  Bank format detection returned None")
            return False

        # Test amount parsing
        test_amounts = [
            ("100.50", ".", 100.50),
            ("1.234,56", ",", 1234.56),
            ("-50.00", ".", -50.00),
            ("(100.00)", ".", -100.00),
            ("EUR 50.00", ".", 50.00),
        ]
        for value, sep, expected in test_amounts:
            result = parse_amount(value, sep)
            if abs(result - expected) > 0.01:
                print(f"  [FAIL] parse_amount('{value}') = {result}, expected {expected}")
                return False
        print("  Amount parsing working")

        # Test date parsing
        test_dates = [
            ("01.01.2025", date(2025, 1, 1)),
            ("2025-01-15", date(2025, 1, 15)),
            ("15/01/2025", date(2025, 1, 15)),
        ]
        for value, expected in test_dates:
            result = parse_date(value, ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'])
            if result != expected:
                print(f"  [FAIL] parse_date('{value}') = {result}, expected {expected}")
                return False
        print("  Date parsing working")

        # Test transaction hash
        hash1 = create_transaction_hash("acc1", "2025-01-01", -50.00, "Test")
        hash2 = create_transaction_hash("acc1", "2025-01-01", -50.00, "Test")
        hash3 = create_transaction_hash("acc1", "2025-01-01", -50.00, "Different")
        if hash1 != hash2:
            print("  [FAIL] Same transactions have different hashes")
            return False
        if hash1 == hash3:
            print("  [FAIL] Different transactions have same hash")
            return False
        print("  Transaction deduplication working")

        # Test supported banks list
        banks = get_supported_banks()
        if len(banks) < 10:
            print(f"  [FAIL] Only {len(banks)} banks supported, expected 10+")
            return False
        print(f"  {len(banks)} bank formats supported")

        print("[PASS] CSV import working correctly")
        return True

    except Exception as e:
        print(f"[FAIL] CSV import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_categorization():
    """Test categorization engine"""
    print("\nTesting categorization...")

    try:
        from categorize import categorize_transaction, load_categories

        # Load categories
        categories = load_categories()
        print(f"  Loaded {len(categories['categories'])} categories")

        # Test transaction
        test_txn = {
            'creditor_name': 'MIGROS ZURICH',
            'description': 'Grocery shopping',
            'amount': -45.50
        }

        category = categorize_transaction(test_txn)
        if category == 'groceries':
            print("[PASS] Transaction categorization working")
            return True
        else:
            print(f"[FAIL] Expected 'groceries', got '{category}'")
            return False

    except Exception as e:
        print(f"[FAIL] Categorization test failed: {e}")
        return False

def test_charts():
    """Test chart generation"""
    print("\nTesting charts...")

    try:
        from charts import create_spending_pie_chart

        test_data = {
            'groceries': 150.0,
            'dining': 80.0,
            'transport': 45.0
        }

        chart_path = create_spending_pie_chart(test_data, "Test Chart")

        if chart_path and Path(chart_path).exists():
            print(f"  Chart created: {chart_path}")
            # Clean up test file
            Path(chart_path).unlink()
            print("[PASS] Chart generation working")
            return True
        else:
            print("[FAIL] Chart creation failed")
            return False

    except Exception as e:
        print(f"[FAIL] Chart test failed: {e}")
        return False

def test_cli():
    """Test CLI interface"""
    print("\nTesting CLI...")

    try:
        from finance import main

        # Test help command
        original_argv = sys.argv
        sys.argv = ['finance.py', '--help']

        try:
            main()
        except SystemExit as e:
            if e.code == 0:
                print("[PASS] CLI help working")
                return True
            else:
                print(f"[FAIL] CLI help failed with code {e.code}")
                return False
        finally:
            sys.argv = original_argv

    except Exception as e:
        print(f"[FAIL] CLI test failed: {e}")
        return False

def test_rate_limiting():
    """Test rate limit enforcement"""
    print("\nTesting rate limiting...")

    try:
        from db import check_rate_limit, record_api_call, get_db

        test_account_id = 'test_rate_limit_account'

        # Clean up any existing test data
        with get_db() as conn:
            conn.execute("DELETE FROM rate_limits WHERE account_id = ?", (test_account_id,))
            conn.commit()

        # First 3 calls should be allowed
        for i in range(3):
            if not check_rate_limit(test_account_id):
                print(f"  [FAIL] Rate limit triggered too early (call {i+1})")
                return False
            record_api_call(test_account_id)

        # 4th call should be blocked
        if check_rate_limit(test_account_id):
            print("  [FAIL] Rate limit not enforced after 3 calls")
            return False

        # Clean up test data
        with get_db() as conn:
            conn.execute("DELETE FROM rate_limits WHERE account_id = ?", (test_account_id,))
            conn.commit()

        print("[PASS] Rate limiting working correctly")
        return True

    except Exception as e:
        print(f"[FAIL] Rate limiting test failed: {e}")
        return False


def test_reminder_system():
    """Test monthly reminder system"""
    print("\nTesting reminder system...")

    try:
        from csv_import import (
            get_reminder_settings, set_reminder_settings,
            should_send_reminder, get_reminder_message
        )

        # Test setting reminders
        set_reminder_settings(enabled=True, day_of_month=15)
        settings = get_reminder_settings()

        if not settings['enabled']:
            print("  [FAIL] Reminder not enabled")
            return False
        if settings['day_of_month'] != 15:
            print(f"  [FAIL] Day is {settings['day_of_month']}, expected 15")
            return False

        print("  Reminder settings working")

        # Test disable
        set_reminder_settings(enabled=False)
        settings = get_reminder_settings()
        if settings['enabled']:
            print("  [FAIL] Reminder not disabled")
            return False

        print("  Reminder enable/disable working")

        # Test should_send (should be False when disabled)
        should_send, reason = should_send_reminder()
        if should_send:
            print("  [FAIL] Should not send when disabled")
            return False

        print("[PASS] Reminder system working correctly")
        return True

    except Exception as e:
        print(f"[FAIL] Reminder test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_currency():
    """Test currency conversion module"""
    print("\nTesting currency conversion...")

    try:
        from currency import (
            get_exchange_rate, convert, format_amount,
            format_with_conversion, get_currency_symbol,
            get_home_currency, set_home_currency
        )
        from db import set_home_currency as db_set_home

        # Test same currency (should return 1.0)
        rate = get_exchange_rate("EUR", "EUR")
        if rate != 1.0:
            print(f"  [FAIL] Same currency rate should be 1.0, got {rate}")
            return False

        # Test currency symbol lookup
        if get_currency_symbol("EUR") != "€":
            print("  [FAIL] EUR symbol should be €")
            return False
        if get_currency_symbol("USD") != "$":
            print("  [FAIL] USD symbol should be $")
            return False

        # Test format_amount
        formatted = format_amount(1234.56, "EUR")
        if "1,234.56" not in formatted and "1234.56" not in formatted:
            print(f"  [FAIL] Format amount failed: {formatted}")
            return False

        # Test home currency setting
        db_set_home("CHF")
        if get_home_currency() != "CHF":
            print("  [FAIL] Home currency not set correctly")
            return False

        # Test conversion (same currency)
        result = convert(100, "CHF", "CHF")
        if result is None or result[0] != 100:
            print("  [FAIL] Same currency conversion failed")
            return False

        print("[PASS] Currency module working correctly")
        return True

    except ImportError as e:
        print(f"  [WARN] Currency module not available: {e}")
        return True  # Not a failure, just not installed

    except Exception as e:
        print(f"[FAIL] Currency test failed: {e}")
        return False


def test_subscriptions():
    """Test subscription management"""
    print("\nTesting subscriptions...")

    try:
        from db import (
            add_subscription, get_subscriptions, delete_subscription,
            get_subscription_by_id, update_subscription, get_subscription_totals
        )
        from subscriptions import (
            cmd_add_subscription, format_subscription_report,
            get_subscription_summary
        )
        import io
        import sys

        # Clean up any existing test subscriptions first
        existing = get_subscriptions(include_cancelled=True)
        for sub in existing:
            if sub['name'] in ['Netflix', 'Claude', 'Adobe', 'Test']:
                delete_subscription(sub['id'])

        # Test add subscription
        sub_id1 = add_subscription(
            name='Netflix',
            amount=15.99,
            currency='EUR',
            billing_cycle='monthly',
            category='streaming'
        )
        if sub_id1 <= 0:
            print("  [FAIL] Failed to add subscription")
            return False
        print("  Subscription add working")

        # Test get subscription by ID
        sub = get_subscription_by_id(sub_id1)
        if not sub or sub['name'] != 'Netflix':
            print("  [FAIL] Failed to retrieve subscription by ID")
            return False
        print("  Subscription retrieval working")

        # Add more subscriptions for totals test
        sub_id2 = add_subscription(
            name='Claude',
            amount=20.00,
            currency='USD',
            billing_cycle='monthly',
            category='ai_productivity'
        )
        sub_id3 = add_subscription(
            name='Adobe',
            amount=599.00,
            currency='EUR',
            billing_cycle='yearly',
            category='ai_productivity'
        )

        # Test totals calculation
        totals = get_subscription_totals()
        if totals['count'] != 3:
            print(f"  [FAIL] Expected 3 subscriptions, got {totals['count']}")
            return False

        # Monthly total should include yearly divided by 12
        # Note: Currency conversion may apply, so just check total > 0 and reasonable range
        # With conversions: ~60-100 depending on exchange rates
        if totals['monthly_total'] < 50 or totals['monthly_total'] > 150:
            print(f"  [FAIL] Monthly total {totals['monthly_total']} outside expected range (50-150)")
            return False
        print(f"  Totals calculation working (monthly: {totals['monthly_total']} {totals['currency']})")

        # Test category grouping
        if 'streaming' not in totals['by_category']:
            print("  [FAIL] Category grouping not working")
            return False
        print("  Category grouping working")

        # Test pause/resume
        update_subscription(sub_id1, status='paused')
        sub = get_subscription_by_id(sub_id1)
        if sub['status'] != 'paused':
            print("  [FAIL] Pause subscription not working")
            return False

        update_subscription(sub_id1, status='active')
        sub = get_subscription_by_id(sub_id1)
        if sub['status'] != 'active':
            print("  [FAIL] Resume subscription not working")
            return False
        print("  Pause/resume working")

        # Test input validation in cmd_add_subscription
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        result = cmd_add_subscription('Test', -10.00, 'monthly')
        output = buffer.getvalue()
        sys.stdout = old_stdout

        if result or 'positive' not in output.lower():
            print("  [FAIL] Negative amount validation not working")
            return False
        print("  Input validation working")

        # Test report formatting
        summary = get_subscription_summary()
        lines = format_subscription_report(summary)
        if not any('Monthly Total' in line for line in lines):
            print("  [FAIL] Report formatting not working")
            return False
        print("  Report formatting working")

        # Cleanup
        delete_subscription(sub_id1)
        delete_subscription(sub_id2)
        delete_subscription(sub_id3)

        # Verify cleanup
        subs = get_subscriptions()
        test_subs = [s for s in subs if s['name'] in ['Netflix', 'Claude', 'Adobe']]
        if test_subs:
            print("  [FAIL] Cleanup failed")
            return False

        print("[PASS] Subscription management working correctly")
        return True

    except Exception as e:
        print(f"[FAIL] Subscription test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crypto():
    """Test crypto wallet module"""
    print("\nTesting crypto wallet module...")

    try:
        # Test imports
        from crypto import (
            get_supported_chains, normalize_chain, format_crypto_value,
            has_zerion_credentials, SUPPORTED_CHAINS
        )
        from db import (
            add_wallet, get_wallets, get_wallet_by_address,
            remove_wallet, save_wallet_snapshot, get_latest_wallet_snapshot,
            get_total_crypto_value
        )

        # Test chain normalization
        if normalize_chain('eth') != 'ethereum':
            print("  [FAIL] Chain normalization failed for 'eth'")
            return False
        if normalize_chain('sol') != 'solana':
            print("  [FAIL] Chain normalization failed for 'sol'")
            return False
        if normalize_chain('matic') != 'polygon':
            print("  [FAIL] Chain normalization failed for 'matic'")
            return False

        # Test supported chains list
        chains = get_supported_chains()
        if 'ethereum' not in chains or 'solana' not in chains:
            print("  [FAIL] Supported chains list incomplete")
            return False

        # Test wallet CRUD operations
        test_address = "0xTestWallet123456789"
        test_chain = "ethereum"
        test_label = "Test Wallet"

        # Add wallet
        if not add_wallet(test_address, test_chain, test_label):
            print("  [FAIL] Failed to add test wallet")
            return False

        # Get wallet
        wallet = get_wallet_by_address(test_address, test_chain)
        if not wallet:
            print("  [FAIL] Failed to retrieve test wallet")
            return False
        if wallet['label'] != test_label:
            print("  [FAIL] Wallet label mismatch")
            return False

        # Test snapshot
        if not save_wallet_snapshot(wallet['id'], 1234.56, '[]'):
            print("  [FAIL] Failed to save wallet snapshot")
            return False

        snapshot = get_latest_wallet_snapshot(wallet['id'])
        if not snapshot or snapshot['total_value_usd'] != 1234.56:
            print("  [FAIL] Snapshot retrieval failed")
            return False

        # Test format_crypto_value (USD case - no conversion needed)
        formatted = format_crypto_value(1234.56, 'USD')
        if '$1,234.56' not in formatted:
            print(f"  [FAIL] Crypto value formatting failed: {formatted}")
            return False

        # Clean up - remove test wallet
        if not remove_wallet(test_address, test_chain):
            print("  [FAIL] Failed to remove test wallet")
            return False

        # Verify removal
        wallet = get_wallet_by_address(test_address, test_chain)
        if wallet:
            print("  [FAIL] Test wallet not properly removed")
            return False

        print("[PASS] Crypto module working correctly")
        return True

    except ImportError as e:
        print(f"  [WARN] Crypto module not available: {e}")
        return True  # Not a failure if module not installed

    except Exception as e:
        print(f"[FAIL] Crypto test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("Personal Finance Skill - Test Suite")
    print("=" * 50)

    tests = [
        test_imports,
        test_database,
        test_csv_import,
        test_categorization,
        test_rate_limiting,
        test_reminder_system,
        test_subscriptions,
        test_currency,
        test_crypto,
        test_charts,
        test_cli
    ]

    passed = 0
    for test in tests:
        if test():
            passed += 1

    print(f"\n{'=' * 50}")
    print(f"Test Results: {passed}/{len(tests)} passed")

    if passed == len(tests):
        print("\nAll tests passed! Finance skill is ready to use.")
        print("\nNext steps:")
        print("1. Run setup wizard:")
        print("   /finance setup")
        print("2. Download CSV from your bank")
        print("3. Import transactions:")
        print("   /finance import <file>")
        return 0
    else:
        print("\nSome tests failed. Check errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
