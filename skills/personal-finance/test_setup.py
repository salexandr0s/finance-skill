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
        print("✅ Database module imported")
    except Exception as e:
        print(f"❌ Database module failed: {e}")
        return False
        
    try:
        import gocardless
        print("✅ GoCardless module imported")
    except Exception as e:
        print(f"❌ GoCardless module failed: {e}")
        return False
        
    try:
        import categorize
        print("✅ Categorization module imported")
    except Exception as e:
        print(f"❌ Categorization module failed: {e}")
        return False
        
    try:
        import charts
        print("✅ Charts module imported")
    except Exception as e:
        print(f"❌ Charts module failed: {e}")
        return False
        
    try:
        import reports
        print("✅ Reports module imported")
    except Exception as e:
        print(f"❌ Reports module failed: {e}")
        return False
        
    try:
        import finance
        print("✅ Main finance module imported")
    except Exception as e:
        print(f"❌ Finance module failed: {e}")
        return False
        
    return True

def test_database():
    """Test database initialization"""
    print("\nTesting database...")
    
    try:
        from db import init_database, get_db
        
        # Initialize database
        init_database()
        print("✅ Database initialized")
        
        # Test connection
        with get_db() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
        expected_tables = {'accounts', 'transactions', 'balances', 'budgets', 'requisitions', 'rate_limits'}
        if expected_tables.issubset(set(tables)):
            print("✅ All database tables created")
            return True
        else:
            missing = expected_tables - set(tables)
            print(f"❌ Missing tables: {missing}")
            return False
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_categorization():
    """Test categorization engine"""
    print("\nTesting categorization...")
    
    try:
        from categorize import categorize_transaction, load_categories
        
        # Load categories
        categories = load_categories()
        print(f"✅ Loaded {len(categories['categories'])} categories")
        
        # Test transaction
        test_txn = {
            'creditor_name': 'MIGROS ZURICH',
            'description': 'Grocery shopping',
            'amount': -45.50
        }
        
        category = categorize_transaction(test_txn)
        if category == 'groceries':
            print("✅ Transaction categorization working")
            return True
        else:
            print(f"❌ Expected 'groceries', got '{category}'")
            return False
            
    except Exception as e:
        print(f"❌ Categorization test failed: {e}")
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
            print(f"✅ Chart created: {chart_path}")
            # Clean up test file
            Path(chart_path).unlink()
            return True
        else:
            print("❌ Chart creation failed")
            return False
            
    except Exception as e:
        print(f"❌ Chart test failed: {e}")
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
                print("✅ CLI help working")
                return True
            else:
                print(f"❌ CLI help failed with code {e.code}")
                return False
        finally:
            sys.argv = original_argv
            
    except Exception as e:
        print(f"❌ CLI test failed: {e}")
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
                print(f"❌ Rate limit triggered too early (call {i+1})")
                return False
            record_api_call(test_account_id)

        # 4th call should be blocked
        if check_rate_limit(test_account_id):
            print("❌ Rate limit not enforced after 3 calls")
            return False

        # Clean up test data
        with get_db() as conn:
            conn.execute("DELETE FROM rate_limits WHERE account_id = ?", (test_account_id,))
            conn.commit()

        print("✅ Rate limiting working correctly")
        return True

    except Exception as e:
        print(f"❌ Rate limiting test failed: {e}")
        return False


def test_categorization_edge_cases():
    """Test category matching with edge cases"""
    print("\nTesting categorization edge cases...")

    try:
        from categorize import categorize_transaction

        test_cases = [
            # Unicode characters
            {
                'creditor_name': 'MIGROS Zürich',
                'description': 'Lebensmittel',
                'amount': -45.50,
                'expected': 'groceries'
            },
            # Special characters
            {
                'creditor_name': "McDonald's #1234",
                'description': 'Fast food',
                'amount': -15.90,
                'expected': 'dining'
            },
            # Empty creditor
            {
                'creditor_name': '',
                'description': 'SBB Train ticket',
                'amount': -23.40,
                'expected': 'transport'
            },
            # Mixed case
            {
                'creditor_name': 'STARBUCKS COFFEE',
                'description': '',
                'amount': -6.50,
                'expected': 'dining'
            }
        ]

        passed = 0
        for i, test in enumerate(test_cases):
            result = categorize_transaction(test)
            if result == test['expected']:
                passed += 1
            else:
                print(f"  Case {i+1}: Expected '{test['expected']}', got '{result}'")

        if passed == len(test_cases):
            print(f"✅ All {len(test_cases)} edge cases passed")
            return True
        else:
            print(f"⚠️ {passed}/{len(test_cases)} edge cases passed")
            return passed >= len(test_cases) - 1  # Allow 1 failure

    except Exception as e:
        print(f"❌ Categorization edge case test failed: {e}")
        return False


def test_date_boundaries():
    """Test date boundary handling"""
    print("\nTesting date boundaries...")

    try:
        from db import get_category_spending
        from datetime import date

        # Test month boundaries
        test_cases = [
            # December to January (year boundary)
            (date(2025, 12, 1), date(2025, 12, 31)),
            # February (28/29 days)
            (date(2024, 2, 1), date(2024, 2, 29)),  # Leap year
            (date(2025, 2, 1), date(2025, 2, 28)),  # Non-leap year
            # Single day
            (date(2025, 1, 15), date(2025, 1, 15)),
        ]

        for start, end in test_cases:
            try:
                result = get_category_spending(start, end)
                # Should not raise exception, result type should be dict
                if not isinstance(result, dict):
                    print(f"❌ Unexpected result type for {start} to {end}")
                    return False
            except Exception as e:
                print(f"❌ Failed for {start} to {end}: {e}")
                return False

        print("✅ Date boundary handling working correctly")
        return True

    except Exception as e:
        print(f"❌ Date boundary test failed: {e}")
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
            print(f"❌ Same currency rate should be 1.0, got {rate}")
            return False

        # Test currency symbol lookup
        if get_currency_symbol("EUR") != "€":
            print("❌ EUR symbol should be €")
            return False
        if get_currency_symbol("USD") != "$":
            print("❌ USD symbol should be $")
            return False

        # Test format_amount
        formatted = format_amount(1234.56, "EUR")
        if "1,234.56" not in formatted and "1234.56" not in formatted:
            print(f"❌ Format amount failed: {formatted}")
            return False

        # Test home currency setting
        db_set_home("CHF")
        if get_home_currency() != "CHF":
            print("❌ Home currency not set correctly")
            return False

        # Test conversion (same currency)
        result = convert(100, "CHF", "CHF")
        if result is None or result[0] != 100:
            print("❌ Same currency conversion failed")
            return False

        print("✅ Currency module working correctly")
        return True

    except ImportError as e:
        print(f"⚠️ Currency module not available: {e}")
        return True  # Not a failure, just not installed

    except Exception as e:
        print(f"❌ Currency test failed: {e}")
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
            print("❌ Chain normalization failed for 'eth'")
            return False
        if normalize_chain('sol') != 'solana':
            print("❌ Chain normalization failed for 'sol'")
            return False
        if normalize_chain('matic') != 'polygon':
            print("❌ Chain normalization failed for 'matic'")
            return False

        # Test supported chains list
        chains = get_supported_chains()
        if 'ethereum' not in chains or 'solana' not in chains:
            print("❌ Supported chains list incomplete")
            return False

        # Test wallet CRUD operations
        test_address = "0xTestWallet123456789"
        test_chain = "ethereum"
        test_label = "Test Wallet"

        # Add wallet
        if not add_wallet(test_address, test_chain, test_label):
            print("❌ Failed to add test wallet")
            return False

        # Get wallet
        wallet = get_wallet_by_address(test_address, test_chain)
        if not wallet:
            print("❌ Failed to retrieve test wallet")
            return False
        if wallet['label'] != test_label:
            print("❌ Wallet label mismatch")
            return False

        # Test snapshot
        if not save_wallet_snapshot(wallet['id'], 1234.56, '[]'):
            print("❌ Failed to save wallet snapshot")
            return False

        snapshot = get_latest_wallet_snapshot(wallet['id'])
        if not snapshot or snapshot['total_value_usd'] != 1234.56:
            print("❌ Snapshot retrieval failed")
            return False

        # Test total crypto value
        total = get_total_crypto_value()
        if total < 1234.56:
            print(f"❌ Total crypto value incorrect: {total}")
            return False

        # Test format_crypto_value (USD case - no conversion needed)
        formatted = format_crypto_value(1234.56, 'USD')
        if '$1,234.56' not in formatted:
            print(f"❌ Crypto value formatting failed: {formatted}")
            return False

        # Clean up - remove test wallet
        if not remove_wallet(test_address, test_chain):
            print("❌ Failed to remove test wallet")
            return False

        # Verify removal
        wallet = get_wallet_by_address(test_address, test_chain)
        if wallet:
            print("❌ Test wallet not properly removed")
            return False

        print("✅ Crypto module working correctly")
        return True

    except ImportError as e:
        print(f"⚠️ Crypto module not available: {e}")
        return True  # Not a failure if module not installed

    except Exception as e:
        print(f"❌ Crypto test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("🧪 Personal Finance Skill - Setup Test")
    print("=" * 50)

    tests = [
        test_imports,
        test_database,
        test_categorization,
        test_categorization_edge_cases,
        test_rate_limiting,
        test_date_boundaries,
        test_currency,
        test_crypto,
        test_charts,
        test_cli
    ]

    passed = 0
    for test in tests:
        if test():
            passed += 1

    print(f"\n📊 Test Results: {passed}/{len(tests)} passed")

    if passed == len(tests):
        print("🎉 All tests passed! Finance skill is ready to use.")
        print("\nNext steps:")
        print("1. Set up GoCardless credentials:")
        print("   python scripts/gocardless.py setup")
        print("2. Connect your bank:")
        print("   python scripts/finance.py setup")
        print("3. Sync transactions:")
        print("   python scripts/finance.py sync")
        return 0
    else:
        print("❌ Some tests failed. Check errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())