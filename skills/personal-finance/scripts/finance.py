#!/usr/bin/env python3
"""
Personal Finance Skill for Claude Code
Main entry point with all finance commands

Supports:
- CSV import from European banks (manual download)
- Crypto wallet tracking via Zerion API
- Budget tracking and spending analysis
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, date

def main():
    parser = argparse.ArgumentParser(description="Personal Finance Commands")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Initial setup wizard')

    # Import command (CSV import)
    import_parser = subparsers.add_parser('import', help='Import transactions from CSV')
    import_parser.add_argument('file', nargs='?', help='Path to CSV file')
    import_parser.add_argument('--account', '-a', help='Account name/ID')
    import_parser.add_argument('--bank', '-b', help='Bank format (auto-detected if not specified)')
    import_parser.add_argument('--currency', '-c', default='EUR', help='Currency code (default: EUR)')
    import_parser.add_argument('--list-banks', action='store_true', help='List supported bank formats')

    # Accounts command
    accounts_parser = subparsers.add_parser('accounts', help='Manage bank accounts')
    accounts_parser.add_argument('action', nargs='?', choices=['list', 'add', 'remove'], default='list')
    accounts_parser.add_argument('--id', help='Account ID (for remove)')

    # Balance command
    balance_parser = subparsers.add_parser('balance', help='Show current balances')

    # Spending command
    spending_parser = subparsers.add_parser('spending', help='Show spending summary')
    spending_parser.add_argument('period', nargs='?', default='month',
                                choices=['today', 'week', 'month'], help='Time period')

    # Report command
    report_parser = subparsers.add_parser('report', help='Generate detailed report')
    report_parser.add_argument('type', nargs='?', default='monthly',
                              choices=['daily', 'weekly', 'monthly'], help='Report type')

    # Budget commands
    budget_parser = subparsers.add_parser('budget', help='Budget operations')
    budget_sub = budget_parser.add_subparsers(dest='budget_action', help='Budget actions')

    budget_set = budget_sub.add_parser('set', help='Set budget for category')
    budget_set.add_argument('category', help='Category name')
    budget_set.add_argument('amount', type=float, help='Monthly budget amount')

    budget_show = budget_sub.add_parser('show', help='Show budget status')

    # Categorize command
    categorize_parser = subparsers.add_parser('categorize', help='Override transaction category')
    categorize_parser.add_argument('transaction_id', help='Transaction ID')
    categorize_parser.add_argument('category', help='New category')

    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare spending between two months')
    compare_parser.add_argument('month1', help='First month (YYYY-MM format)')
    compare_parser.add_argument('month2', nargs='?', help='Second month (YYYY-MM format, defaults to previous month)')

    # Currency command
    currency_parser = subparsers.add_parser('currency', help='Set or show home currency')
    currency_parser.add_argument('code', nargs='?', help='Currency code (e.g., EUR, USD, CHF). Omit to show current.')

    # Reminder command
    reminder_parser = subparsers.add_parser('reminder', help='Manage monthly import reminders')
    reminder_parser.add_argument('action', nargs='?', choices=['status', 'enable', 'disable', 'set-day'], default='status')
    reminder_parser.add_argument('--day', type=int, help='Day of month for reminder (1-28)')

    # Wallet commands
    wallet_parser = subparsers.add_parser('wallet', help='Crypto wallet operations')
    wallet_sub = wallet_parser.add_subparsers(dest='wallet_action', help='Wallet actions')

    wallet_add = wallet_sub.add_parser('add', help='Add wallet address')
    wallet_add.add_argument('address', help='Wallet address')
    wallet_add.add_argument('--chain', default='ethereum', help='Blockchain (ethereum, solana, polygon, etc.)')
    wallet_add.add_argument('--label', help='Friendly name for wallet')

    wallet_remove = wallet_sub.add_parser('remove', help='Remove wallet')
    wallet_remove.add_argument('address', help='Wallet address to remove')

    wallet_show = wallet_sub.add_parser('show', help='Show wallet balances')
    wallet_show.add_argument('--detailed', action='store_true', help='Show token breakdown')

    wallet_sync = wallet_sub.add_parser('sync', help='Force refresh wallet data')

    wallet_list = wallet_sub.add_parser('list', help='List all wallets')

    args = parser.parse_args()

    if args.command == 'setup':
        return cmd_setup()
    elif args.command == 'import':
        if args.list_banks:
            return cmd_list_banks()
        return cmd_import(args.file, args.account, args.bank, args.currency)
    elif args.command == 'accounts':
        if args.action == 'remove' and args.id:
            return cmd_account_remove(args.id)
        return cmd_accounts()
    elif args.command == 'balance':
        return cmd_balance()
    elif args.command == 'spending':
        return cmd_spending(args.period)
    elif args.command == 'report':
        return cmd_report(args.type)
    elif args.command == 'budget':
        if args.budget_action == 'set':
            return cmd_budget_set(args.category, args.amount)
        elif args.budget_action == 'show':
            return cmd_budget_show()
        else:
            budget_parser.print_help()
            return 1
    elif args.command == 'categorize':
        return cmd_categorize(args.transaction_id, args.category)
    elif args.command == 'compare':
        return cmd_compare(args.month1, args.month2)
    elif args.command == 'currency':
        return cmd_currency(args.code)
    elif args.command == 'reminder':
        return cmd_reminder(args.action, args.day)
    elif args.command == 'wallet':
        if args.wallet_action == 'add':
            return cmd_wallet_add(args.address, args.chain, args.label)
        elif args.wallet_action == 'remove':
            return cmd_wallet_remove(args.address)
        elif args.wallet_action == 'show':
            return cmd_wallet_show(args.detailed)
        elif args.wallet_action == 'sync':
            return cmd_wallet_sync()
        elif args.wallet_action == 'list':
            return cmd_wallet_list()
        else:
            wallet_parser.print_help()
            return 1
    else:
        parser.print_help()
        return 1


# ============================================================================
# Setup & Import Commands
# ============================================================================

def cmd_setup() -> int:
    """Interactive onboarding flow"""
    print("=" * 60)
    print("Welcome to Personal Finance Skill Setup!")
    print("=" * 60)
    print()
    print("This skill helps you track spending from:")
    print("  - Bank accounts (via CSV export)")
    print("  - Crypto wallets (via Zerion API)")
    print()
    print("For European banks, we use CSV import because Open Banking")
    print("APIs require business registration. CSV works great and")
    print("keeps your data fully private!")
    print()

    # Step 1: Set home currency
    print("-" * 60)
    print("STEP 1: Choose Your Home Currency")
    print("-" * 60)
    print()
    print("All amounts will be displayed in your chosen currency.")
    print("Common options: EUR, USD, GBP, CHF, JPY")
    print()

    try:
        from currency import get_supported_currencies, get_currency_symbol
        from db import set_home_currency, get_home_currency

        current = get_home_currency()
        currency_input = input(f"Enter currency code [{current}]: ").strip().upper()

        if currency_input:
            supported = get_supported_currencies()
            if currency_input in supported:
                set_home_currency(currency_input)
                symbol = get_currency_symbol(currency_input)
                print(f"Home currency set to: {currency_input} ({symbol})")
            else:
                print(f"Unknown currency '{currency_input}', keeping {current}")
        else:
            print(f"Keeping current currency: {current}")

    except ImportError as e:
        print(f"Currency module not available: {e}")
    except Exception as e:
        print(f"Error setting currency: {e}")

    # Step 2: Create first account
    print()
    print("-" * 60)
    print("STEP 2: Create Your First Bank Account")
    print("-" * 60)
    print()
    print("Give your account a name (e.g., 'Main Checking', 'Savings')")
    print()

    account_name = input("Account name: ").strip()
    if not account_name:
        account_name = "Main Account"

    # Create account ID from name
    import hashlib
    account_id = hashlib.md5(account_name.lower().encode()).hexdigest()[:12]

    try:
        from db import store_csv_account, get_home_currency
        currency = get_home_currency()
        store_csv_account(account_id, account_name, currency)
        print(f"Account '{account_name}' created!")
    except Exception as e:
        print(f"Error creating account: {e}")

    # Step 3: Import instructions
    print()
    print("-" * 60)
    print("STEP 3: Import Your First Transactions")
    print("-" * 60)
    print()
    print("To import transactions:")
    print()
    print("  1. Log into your bank's online banking")
    print("  2. Go to account statements or transaction history")
    print("  3. Export/download as CSV (usually last 1-3 months)")
    print("  4. Share the CSV file with me!")
    print()
    print("I support 20+ European banks including:")
    print("  - UBS, Credit Suisse, PostFinance, Raiffeisen (CH)")
    print("  - Deutsche Bank, Sparkasse, Commerzbank, ING (DE)")
    print("  - BNP Paribas, Societe Generale, Credit Agricole (FR)")
    print("  - Barclays, HSBC, Lloyds (UK)")
    print("  - ING, Rabobank, ABN AMRO (NL)")
    print()
    print("Format is auto-detected, so just share the file!")
    print()

    # Step 4: Set up monthly reminders
    print("-" * 60)
    print("STEP 4: Monthly Import Reminders")
    print("-" * 60)
    print()
    print("I can remind you to import your bank statements each month.")
    print()

    enable_reminder = input("Enable monthly reminders? (y/n) [y]: ").strip().lower()
    if enable_reminder != 'n':
        try:
            from csv_import import set_reminder_settings
            set_reminder_settings(enabled=True, day_of_month=28)
            print("Monthly reminders enabled (day 28 of each month)")
        except Exception as e:
            print(f"Could not set reminders: {e}")
    else:
        try:
            from csv_import import set_reminder_settings
            set_reminder_settings(enabled=False)
        except Exception:
            pass

    # Step 5: Crypto (optional)
    print()
    print("-" * 60)
    print("STEP 5: Add Crypto Wallets (Optional)")
    print("-" * 60)
    print()
    print("Track your crypto portfolio alongside bank accounts.")
    print("Supported: Ethereum, Solana, Polygon, Arbitrum, Base, and more")
    print()

    add_crypto = input("Would you like to add a crypto wallet? (y/n): ").strip().lower()
    if add_crypto == 'y':
        try:
            from crypto import (
                has_zerion_credentials, save_zerion_api_key, get_supported_chains,
                normalize_chain, ZerionClient
            )
            from db import add_wallet

            # Check for Zerion API key
            if not has_zerion_credentials():
                print()
                print("To track crypto wallets, you need a free Zerion API key:")
                print("Go to: https://developers.zerion.io")
                print("  1. Sign up for free (no credit card required)")
                print("  2. Get your API key from the dashboard")
                print()
                api_key = input("Enter your Zerion API key: ").strip()
                if api_key:
                    if save_zerion_api_key(api_key):
                        print("API key saved!")
                    else:
                        print("Could not save API key, skipping crypto setup.")
                        add_crypto = 'n'
                else:
                    print("No API key provided, skipping crypto setup.")
                    add_crypto = 'n'

            # Add wallets in a loop
            if add_crypto == 'y':
                print()
                print("Supported chains:", ", ".join(get_supported_chains()[:8]), "...")
                while True:
                    print()
                    address = input("Wallet address (or press Enter to finish): ").strip()
                    if not address:
                        break

                    chain = input("Blockchain [ethereum]: ").strip().lower() or 'ethereum'
                    label = input("Label (optional): ").strip() or None

                    chain_normalized = normalize_chain(chain)

                    # Validate and add wallet
                    print("Validating wallet...")
                    try:
                        client = ZerionClient()
                        client.get_portfolio(address)
                        print("Wallet validated!")

                        if add_wallet(address, chain_normalized, label):
                            display = label or f"{address[:6]}...{address[-4:]}"
                            print(f"Added: {display} on {chain_normalized}")
                        else:
                            print("Wallet already exists or could not be added")
                    except Exception as e:
                        print(f"Could not validate wallet: {e}")
                        add_anyway = input("Add anyway? (y/n): ").strip().lower()
                        if add_anyway == 'y':
                            if add_wallet(address, chain_normalized, label):
                                print("Wallet added (unvalidated)")
        except ImportError as e:
            print(f"Crypto module not available: {e}")
    else:
        print("Skipping crypto setup. You can add wallets later with:")
        print("  /finance wallet add <address> --chain ethereum --label 'My Wallet'")

    # Done!
    print()
    print("=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Download a CSV from your bank")
    print("  2. Share it with me to import transactions")
    print()
    print("Available commands:")
    print("  /finance import <file>  - Import bank CSV")
    print("  /finance spending       - See spending summary")
    print("  /finance balance        - View account balances")
    print("  /finance report         - Generate detailed reports")
    print("  /finance accounts       - List your accounts")
    print()
    return 0


def cmd_import(file_path: str = None, account: str = None,
               bank_format: str = None, currency: str = 'EUR') -> int:
    """Import transactions from CSV file"""

    if not file_path:
        print("CSV Import")
        print("=" * 50)
        print()
        print("To import transactions, share a CSV file with me!")
        print()
        print("Usage: /finance import <file> [--account NAME] [--bank FORMAT]")
        print()
        print("Options:")
        print("  --account, -a  Account name (auto-created if new)")
        print("  --bank, -b     Bank format (auto-detected if not specified)")
        print("  --currency, -c Currency code (default: EUR)")
        print()
        print("Use '/finance import --list-banks' to see supported banks.")
        return 0

    try:
        from csv_import import import_csv_file, get_supported_banks
        from db import get_csv_accounts
        import hashlib

        # Resolve file path
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            print(f"File not found: {file_path}")
            return 1

        if not path.suffix.lower() == '.csv':
            print(f"File must be a CSV: {file_path}")
            return 1

        # Determine account
        if not account:
            # Check existing accounts
            existing = get_csv_accounts()
            if existing:
                print("Select an account or create new:")
                for i, acc in enumerate(existing, 1):
                    print(f"  {i}. {acc['name']} ({acc['transaction_count']} transactions)")
                print(f"  {len(existing) + 1}. Create new account")
                print()

                choice = input(f"Choice [1]: ").strip()
                if not choice:
                    choice = "1"

                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(existing):
                        account = existing[idx]['name']
                        account_id = existing[idx]['id']
                    else:
                        account = input("New account name: ").strip() or "Imported Account"
                        account_id = hashlib.md5(account.lower().encode()).hexdigest()[:12]
                except ValueError:
                    account = choice  # Use input as account name
                    account_id = hashlib.md5(account.lower().encode()).hexdigest()[:12]
            else:
                account = input("Account name [Main Account]: ").strip() or "Main Account"
                account_id = hashlib.md5(account.lower().encode()).hexdigest()[:12]
        else:
            account_id = hashlib.md5(account.lower().encode()).hexdigest()[:12]

        print()
        print(f"Importing: {path.name}")
        print(f"Account: {account}")
        print()

        # Do the import
        result = import_csv_file(
            str(path),
            account_id,
            account_name=account,
            bank_format=bank_format,
            currency=currency
        )

        if result['success']:
            print(f"Bank format: {result['bank_name']}")
            print(f"Total rows: {result['total_rows']}")
            print(f"Imported: {result['imported']} new transactions")
            print(f"Duplicates skipped: {result['duplicates']}")

            if result['error_count'] > 0:
                print(f"Errors: {result['error_count']}")
                for err in result['errors'][:5]:
                    print(f"  - {err}")

            if result['imported'] > 0:
                print()
                print("Run '/finance spending' to see your spending summary!")

            return 0
        else:
            print(f"Import failed: {result.get('error', 'Unknown error')}")
            return 1

    except Exception as e:
        print(f"Error importing CSV: {e}")
        return 1


def cmd_list_banks() -> int:
    """List supported bank formats"""
    try:
        from csv_import import get_supported_banks

        banks = get_supported_banks()

        print("Supported Bank Formats")
        print("=" * 50)
        print()
        print("Format is auto-detected in most cases.")
        print("Use --bank <key> to force a specific format.")
        print()

        # Group by country
        swiss = [b for b in banks if 'ch' in b['key'] or b['key'] in ['ubs', 'credit_suisse', 'postfinance']]
        german = [b for b in banks if b['key'] in ['deutsche_bank', 'sparkasse', 'commerzbank', 'ing_diba']]
        french = [b for b in banks if b['key'] in ['bnp_paribas', 'societe_generale', 'credit_agricole']]
        uk = [b for b in banks if b['key'] in ['barclays', 'hsbc', 'lloyds']]
        dutch = [b for b in banks if b['key'] in ['ing_nl', 'rabobank', 'abn_amro']]
        austrian = [b for b in banks if b['key'] in ['erste_bank']]

        if swiss:
            print("Switzerland:")
            for b in swiss:
                print(f"  {b['key']:<20} {b['name']}")

        if german:
            print("\nGermany:")
            for b in german:
                print(f"  {b['key']:<20} {b['name']}")

        if french:
            print("\nFrance:")
            for b in french:
                print(f"  {b['key']:<20} {b['name']}")

        if uk:
            print("\nUnited Kingdom:")
            for b in uk:
                print(f"  {b['key']:<20} {b['name']}")

        if dutch:
            print("\nNetherlands:")
            for b in dutch:
                print(f"  {b['key']:<20} {b['name']}")

        if austrian:
            print("\nAustria:")
            for b in austrian:
                print(f"  {b['key']:<20} {b['name']}")

        print()
        print("Don't see your bank? Try anyway - 'generic' format")
        print("handles most standard CSV exports.")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


# ============================================================================
# Account Commands
# ============================================================================

def cmd_accounts() -> int:
    """List all accounts"""
    try:
        from db import get_csv_accounts, get_wallets

        csv_accounts = get_csv_accounts()
        wallets = get_wallets()

        if not csv_accounts and not wallets:
            print("No accounts configured.")
            print()
            print("To add a bank account:")
            print("  1. Download CSV from your bank")
            print("  2. Run: /finance import <file>")
            print()
            print("To add a crypto wallet:")
            print("  Run: /finance wallet add <address>")
            return 0

        print("Your Accounts")
        print("=" * 60)

        if csv_accounts:
            print()
            print("Bank Accounts (CSV Import)")
            print("-" * 40)
            for acc in csv_accounts:
                print(f"  {acc['name']}")
                print(f"    ID: {acc['id']}")
                print(f"    Transactions: {acc['transaction_count'] or 0}")
                if acc['latest_transaction']:
                    print(f"    Latest: {acc['latest_transaction']}")
                if acc['oldest_transaction']:
                    print(f"    Range: {acc['oldest_transaction']} to {acc['latest_transaction']}")
                print()

        if wallets:
            print("Crypto Wallets")
            print("-" * 40)
            for w in wallets:
                label = w['label'] or f"{w['address'][:8]}..."
                print(f"  {label}")
                print(f"    Chain: {w['blockchain']}")
                print(f"    Address: {w['address'][:12]}...{w['address'][-6:]}")
                print()

        return 0

    except Exception as e:
        print(f"Error listing accounts: {e}")
        return 1


def cmd_account_remove(account_id: str) -> int:
    """Remove a CSV account"""
    try:
        from db import delete_csv_account, get_csv_accounts

        # Find account
        accounts = get_csv_accounts()
        account = None
        for acc in accounts:
            if acc['id'] == account_id or acc['name'].lower() == account_id.lower():
                account = acc
                break

        if not account:
            print(f"Account not found: {account_id}")
            return 1

        print(f"Remove account: {account['name']}")
        print(f"  Transactions: {account['transaction_count'] or 0}")
        print()

        confirm = input("This will delete all transactions. Continue? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return 0

        if delete_csv_account(account['id']):
            print(f"Account '{account['name']}' removed.")
            return 0
        else:
            print("Failed to remove account.")
            return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1


# ============================================================================
# Balance & Spending Commands
# ============================================================================

def cmd_balance() -> int:
    """Show current balances"""
    try:
        from db import get_csv_accounts, get_total_crypto_value
        from crypto import format_crypto_value, has_zerion_credentials

        accounts = get_csv_accounts()

        print("Account Balances")
        print("=" * 50)

        if accounts:
            print()
            print("Bank Accounts (from imported transactions)")
            print("-" * 40)

            for acc in accounts:
                # Calculate balance from transactions (income - spending)
                income = acc.get('total_income', 0) or 0
                spending = acc.get('total_spending', 0) or 0
                # Note: This is just net flow, not actual balance
                print(f"  {acc['name']}")
                print(f"    Total income: +{income:,.2f} {acc['currency']}")
                print(f"    Total spending: -{spending:,.2f} {acc['currency']}")
                print(f"    Net flow: {income - spending:,.2f} {acc['currency']}")
                print()

            print("  Note: These are totals from imported transactions,")
            print("  not actual account balances.")

        # Crypto balances
        if has_zerion_credentials():
            try:
                total_crypto = get_total_crypto_value()
                if total_crypto > 0:
                    print()
                    print("Crypto Wallets")
                    print("-" * 40)
                    print(f"  Total: {format_crypto_value(total_crypto)}")
                    print()
                    print("  Run '/finance wallet show' for details.")
            except Exception:
                pass

        if not accounts:
            print()
            print("No transactions imported yet.")
            print("Run '/finance import <csv>' to import bank statements.")

        return 0

    except Exception as e:
        print(f"Error fetching balances: {e}")
        return 1


def cmd_spending(period: str) -> int:
    """Show spending summary"""
    try:
        from db import get_category_spending
        from datetime import timedelta

        # Calculate date range
        today = date.today()
        if period == 'today':
            start_date = end_date = today
        elif period == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif period == 'month':
            start_date = today.replace(day=1)
            end_date = today

        spending = get_category_spending(start_date, end_date)
        if not spending:
            print(f"No spending data for {period}")
            print()
            print("Import bank transactions with: /finance import <csv>")
            return 0

        total_spent = sum(amount for amount in spending.values())

        print(f"Spending Summary - {period.title()}")
        print(f"({start_date} to {end_date})")
        print("=" * 50)
        print()

        # Sort by amount, descending
        for category, amount in sorted(spending.items(), key=lambda x: x[1], reverse=True):
            percentage = (amount / total_spent) * 100 if total_spent > 0 else 0
            emoji = get_category_emoji(category)
            bar = "=" * int(percentage / 5)  # Simple bar chart
            print(f"{emoji} {category.title():<15} {amount:>10,.2f}  {percentage:>5.1f}%  {bar}")

        print("-" * 50)
        print(f"   {'Total':<15} {total_spent:>10,.2f}")

        # Simple anomaly detection
        anomalies = detect_spending_anomalies(spending, period)
        if anomalies:
            print()
            print("Unusual Spending:")
            for category, data in anomalies.items():
                print(f"  {category.title()}: {data['current']:,.2f} "
                      f"(+{data['increase']:.0f}% vs average)")

        return 0

    except Exception as e:
        print(f"Error fetching spending: {e}")
        return 1


def cmd_report(report_type: str) -> int:
    """Generate detailed report"""
    try:
        sys.path.append(str(Path(__file__).parent.parent / 'templates'))
        from reports import generate_report
        from charts import create_spending_pie_chart, cleanup_old_charts

        print(f"Generating {report_type} report...")

        report = generate_report(report_type)
        if not report:
            print(f"Could not generate {report_type} report")
            print("Make sure you have imported some transactions first.")
            return 1

        # Print text report
        print(report.text)

        # Generate and save chart
        if report.chart_data:
            chart_path = create_spending_pie_chart(report.chart_data,
                                                 f"{report_type.title()} Spending")
            if chart_path:
                print(f"Chart saved: {chart_path}")
                print(f"View chart: open {chart_path}")

        # Clean up old charts (keep last 7 days)
        cleanup_old_charts(days_to_keep=7)

        return 0

    except ImportError as e:
        print(f"Required module not available: {e}")
        return 1
    except Exception as e:
        print(f"Error generating report: {e}")
        return 1


# ============================================================================
# Budget Commands
# ============================================================================

def cmd_budget_set(category: str, amount: float) -> int:
    """Set budget for category"""
    try:
        from db import set_category_budget

        success = set_category_budget(category.lower(), amount)
        if success:
            print(f"Budget set: {category.title()} = {amount:,.2f}/month")
            return 0
        else:
            print(f"Failed to set budget for {category}")
            return 1

    except Exception as e:
        print(f"Error setting budget: {e}")
        return 1


def cmd_budget_show() -> int:
    """Show budget status"""
    try:
        from db import get_budget_status

        # Get current month spending vs budgets
        today = date.today()
        start_date = today.replace(day=1)

        budgets = get_budget_status(start_date, today)
        if not budgets:
            print("No budgets set.")
            print()
            print("Use '/finance budget set <category> <amount>' to create one.")
            print()
            print("Example categories: groceries, dining, transport, shopping,")
            print("                   subscriptions, utilities, entertainment")
            return 0

        print("Budget Status - Current Month")
        print("=" * 50)
        print()

        for budget in budgets:
            category = budget['category']
            limit = budget['monthly_limit']
            spent = budget['spent']
            percentage = (spent / limit) * 100 if limit > 0 else 0
            remaining = limit - spent

            if percentage > 100:
                status = "[OVER]"
            elif percentage > 80:
                status = "[WARNING]"
            else:
                status = "[OK]"

            emoji = get_category_emoji(category)
            print(f"{emoji} {category.title()} {status}")
            print(f"   Spent: {spent:,.2f} / {limit:,.2f} ({percentage:.0f}%)")
            print(f"   Remaining: {remaining:,.2f}")
            print()

        return 0

    except Exception as e:
        print(f"Error showing budgets: {e}")
        return 1


def cmd_categorize(transaction_id: str, category: str) -> int:
    """Override transaction category"""
    try:
        from db import set_transaction_category

        success = set_transaction_category(transaction_id, category.lower())
        if success:
            print(f"Transaction {transaction_id[:8]}... categorized as '{category.title()}'")
            return 0
        else:
            print(f"Transaction {transaction_id} not found")
            return 1

    except Exception as e:
        print(f"Error categorizing transaction: {e}")
        return 1


def cmd_compare(month1: str, month2: str = None) -> int:
    """Compare spending between two months"""
    try:
        from db import get_category_spending
        from datetime import timedelta

        # Parse month1
        try:
            year1, mon1 = map(int, month1.split('-'))
            start1 = date(year1, mon1, 1)
            if mon1 == 12:
                end1 = date(year1 + 1, 1, 1) - timedelta(days=1)
            else:
                end1 = date(year1, mon1 + 1, 1) - timedelta(days=1)
        except (ValueError, AttributeError):
            print(f"Invalid month format: {month1}. Use YYYY-MM format.")
            return 1

        # Parse month2 or default to previous month
        if month2:
            try:
                year2, mon2 = map(int, month2.split('-'))
                start2 = date(year2, mon2, 1)
                if mon2 == 12:
                    end2 = date(year2 + 1, 1, 1) - timedelta(days=1)
                else:
                    end2 = date(year2, mon2 + 1, 1) - timedelta(days=1)
            except (ValueError, AttributeError):
                print(f"Invalid month format: {month2}. Use YYYY-MM format.")
                return 1
        else:
            # Default to month before month1
            if mon1 == 1:
                start2 = date(year1 - 1, 12, 1)
                end2 = date(year1, 1, 1) - timedelta(days=1)
            else:
                start2 = date(year1, mon1 - 1, 1)
                end2 = start1 - timedelta(days=1)

        spending1 = get_category_spending(start1, end1)
        spending2 = get_category_spending(start2, end2)

        print(f"Spending Comparison")
        print(f"{start1.strftime('%B %Y')} vs {start2.strftime('%B %Y')}")
        print("=" * 60)
        print()

        total1 = sum(spending1.values())
        total2 = sum(spending2.values())

        all_categories = set(spending1.keys()) | set(spending2.keys())

        print(f"{'Category':<15} {'Current':>10} {'Previous':>10} {'Change':>12}")
        print("-" * 60)

        for category in sorted(all_categories):
            amt1 = spending1.get(category, 0)
            amt2 = spending2.get(category, 0)
            diff = amt1 - amt2
            pct = ((diff / amt2) * 100) if amt2 > 0 else (100 if amt1 > 0 else 0)

            emoji = get_category_emoji(category)
            arrow = "^" if diff > 0 else "v" if diff < 0 else "="

            print(f"{emoji} {category.title():<12} {amt1:>10,.0f} {amt2:>10,.0f}  {arrow} {diff:+,.0f} ({pct:+.0f}%)")

        print("-" * 60)
        total_diff = total1 - total2
        total_pct = ((total_diff / total2) * 100) if total2 > 0 else 0
        print(f"   {'Total':<12} {total1:>10,.0f} {total2:>10,.0f}  {'+' if total_diff >= 0 else ''}{total_diff:,.0f} ({total_pct:+.0f}%)")

        return 0

    except Exception as e:
        print(f"Error comparing months: {e}")
        return 1


def cmd_currency(code: str = None) -> int:
    """Set or show home currency"""
    try:
        from currency import (
            get_home_currency, get_currency_symbol,
            get_supported_currencies, format_amount
        )
        from db import set_home_currency as db_set_home

        current = get_home_currency()

        if code is None:
            # Show current currency
            symbol = get_currency_symbol(current)
            print(f"Home Currency: {current} ({symbol})")
            print(f"\nAll amounts will be displayed in {current}.")
            print(f"Use '/finance currency <CODE>' to change (e.g., EUR, USD, CHF)")
            return 0

        code = code.upper()

        # Validate currency code
        supported = get_supported_currencies()
        if code not in supported:
            print(f"Unknown currency: {code}")
            print(f"Supported currencies include: EUR, USD, GBP, CHF, JPY, ...")
            return 1

        # Set new currency
        db_set_home(code)
        symbol = get_currency_symbol(code)

        print(f"Home currency set to: {code} ({symbol})")

        return 0

    except Exception as e:
        print(f"Error setting currency: {e}")
        return 1


# ============================================================================
# Reminder Commands
# ============================================================================

def cmd_reminder(action: str, day: int = None) -> int:
    """Manage monthly import reminders"""
    try:
        from csv_import import (
            get_reminder_settings, set_reminder_settings,
            should_send_reminder, get_reminder_message
        )

        if action == 'status':
            settings = get_reminder_settings()
            should_send, reason = should_send_reminder()

            print("Monthly Import Reminder Status")
            print("=" * 40)
            print()
            print(f"Enabled: {'Yes' if settings['enabled'] else 'No'}")
            print(f"Reminder day: {settings['day_of_month']} of each month")
            if settings['last_reminder_sent']:
                print(f"Last sent: {settings['last_reminder_sent']}")
            print()
            print(f"Should send now: {'Yes' if should_send else 'No'}")
            print(f"Reason: {reason}")

            if should_send:
                print()
                print("-" * 40)
                print(get_reminder_message())

            return 0

        elif action == 'enable':
            set_reminder_settings(enabled=True)
            print("Monthly reminders enabled!")
            return 0

        elif action == 'disable':
            set_reminder_settings(enabled=False)
            print("Monthly reminders disabled.")
            return 0

        elif action == 'set-day':
            if day is None:
                print("Please specify a day: /finance reminder set-day --day 28")
                return 1
            if day < 1 or day > 28:
                print("Day must be between 1 and 28.")
                return 1
            set_reminder_settings(day_of_month=day)
            print(f"Reminder day set to: {day}")
            return 0

        else:
            print(f"Unknown action: {action}")
            return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1


# ============================================================================
# Crypto Wallet Commands
# ============================================================================

def cmd_wallet_add(address: str, chain: str, label: str = None) -> int:
    """Add a crypto wallet address"""
    try:
        from db import add_wallet, get_wallet_by_address
        from crypto import (
            has_zerion_credentials, save_zerion_api_key,
            normalize_chain, get_supported_chains, ZerionClient
        )

        # Check if Zerion API key is configured
        if not has_zerion_credentials():
            print("Zerion API key not configured.")
            print()
            print("To track crypto wallets, you need a free Zerion API key:")
            print("Go to: https://developers.zerion.io")
            print("  1. Sign up for free")
            print("  2. Get your API key from the dashboard")
            print()
            api_key = input("Enter your Zerion API key (or press Enter to skip): ").strip()
            if not api_key:
                print("Wallet not added. Configure API key first.")
                return 1
            if not save_zerion_api_key(api_key):
                print("Failed to save API key")
                return 1
            print("API key saved!")
            print()

        # Normalize chain name
        chain_normalized = normalize_chain(chain)
        supported = get_supported_chains()
        if chain.lower() not in [c.lower() for c in supported]:
            print(f"Chain '{chain}' may not be fully supported.")
            print(f"Supported chains: {', '.join(supported[:8])}...")

        # Check if wallet already exists
        existing = get_wallet_by_address(address, chain_normalized)
        if existing:
            print(f"Wallet already exists: {existing.get('label', address[:8])}")
            return 1

        # Validate address by fetching portfolio
        print(f"Validating wallet address...")
        try:
            client = ZerionClient()
            portfolio = client.get_portfolio(address)
            print("Wallet validated!")
        except Exception as e:
            print(f"Could not validate wallet (may still work): {e}")

        # Add wallet to database
        if add_wallet(address, chain_normalized, label):
            display_name = label or f"{address[:6]}...{address[-4:]}"
            print(f"Wallet added: {display_name} on {chain_normalized}")
            print()
            print("Run '/finance wallet sync' to fetch balances")
            return 0
        else:
            print("Failed to add wallet")
            return 1

    except ImportError as e:
        print(f"Required module not available: {e}")
        return 1
    except Exception as e:
        print(f"Error adding wallet: {e}")
        return 1


def cmd_wallet_remove(address: str) -> int:
    """Remove a crypto wallet"""
    try:
        from db import remove_wallet, get_wallet_by_address

        # Find wallet
        wallet = get_wallet_by_address(address)
        if not wallet:
            print(f"Wallet not found: {address[:8]}...")
            return 1

        # Confirm removal
        label = wallet.get('label') or f"{address[:6]}...{address[-4:]}"
        confirm = input(f"Remove wallet '{label}'? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return 0

        if remove_wallet(address):
            print(f"Wallet removed: {label}")
            return 0
        else:
            print("Failed to remove wallet")
            return 1

    except Exception as e:
        print(f"Error removing wallet: {e}")
        return 1


def cmd_wallet_show(detailed: bool = False) -> int:
    """Show crypto wallet balances"""
    try:
        from crypto import format_wallet_summary, has_zerion_credentials
        from db import get_wallets

        wallets = get_wallets()
        if not wallets:
            print("No crypto wallets configured.")
            print("Use '/finance wallet add <address>' to add one.")
            return 0

        if not has_zerion_credentials():
            print("Zerion API key not configured. Run '/finance wallet add' to set up.")
            return 1

        summary = format_wallet_summary(include_positions=detailed)
        print(summary)
        return 0

    except Exception as e:
        print(f"Error showing wallets: {e}")
        return 1


def cmd_wallet_sync() -> int:
    """Sync all crypto wallets"""
    try:
        from crypto import sync_all_wallets, has_zerion_credentials, format_crypto_value
        from db import get_wallets

        wallets = get_wallets()
        if not wallets:
            print("No crypto wallets configured.")
            print("Use '/finance wallet add <address>' to add one.")
            return 0

        if not has_zerion_credentials():
            print("Zerion API key not configured. Run '/finance wallet add' to set up.")
            return 1

        print(f"Syncing {len(wallets)} wallet(s)...")
        print()

        results = sync_all_wallets(force=True)

        total = 0.0
        for wallet in wallets:
            wallet_id = wallet['id']
            label = wallet['label'] or f"{wallet['blockchain'].title()} Wallet"
            value = results.get(wallet_id, 0)
            total += value

            value_str = format_crypto_value(value)
            print(f"  {label}: {value_str}")

        print()
        total_str = format_crypto_value(total)
        print(f"Total Crypto: {total_str}")
        return 0

    except Exception as e:
        print(f"Error syncing wallets: {e}")
        return 1


def cmd_wallet_list() -> int:
    """List all configured wallets"""
    try:
        from db import get_wallets, get_latest_wallet_snapshot

        wallets = get_wallets()
        if not wallets:
            print("No crypto wallets configured.")
            print("Use '/finance wallet add <address>' to add one.")
            return 0

        print("Configured Wallets")
        print("=" * 60)

        for wallet in wallets:
            label = wallet['label'] or 'Unnamed'
            chain = wallet['blockchain'].title()
            address = wallet['address']
            address_short = f"{address[:10]}...{address[-6:]}"
            created = wallet['created_at'][:10] if wallet.get('created_at') else 'Unknown'

            snapshot = get_latest_wallet_snapshot(wallet['id'])
            last_sync = snapshot['snapshot_date'] if snapshot else 'Never'
            value = f"${snapshot['total_value_usd']:,.2f}" if snapshot else 'Not synced'

            print(f"\n  {label}")
            print(f"    Chain: {chain}")
            print(f"    Address: {address_short}")
            print(f"    Value: {value}")
            print(f"    Added: {created} | Last sync: {last_sync}")

        return 0

    except Exception as e:
        print(f"Error listing wallets: {e}")
        return 1


# ============================================================================
# Helper Functions
# ============================================================================

def get_category_emoji(category: str) -> str:
    """Get emoji for category"""
    emojis = {
        'groceries': '[G]',
        'dining': '[D]',
        'transport': '[T]',
        'shopping': '[S]',
        'subscriptions': '[SUB]',
        'utilities': '[U]',
        'entertainment': '[E]',
        'health': '[H]',
        'housing': '[HOU]',
        'income': '[+]',
        'transfer': '[<>]',
        'other': '[O]'
    }
    return emojis.get(category.lower(), '[?]')


def detect_spending_anomalies(current_spending: Dict[str, float], period: str) -> Dict[str, Dict]:
    """Simple anomaly detection - flag spending > 2x average for category"""
    try:
        from db import get_historical_category_averages

        averages = get_historical_category_averages(period, num_periods=6)  # Last 6 periods
        anomalies = {}

        for category, current_amount in current_spending.items():
            if category in averages:
                avg_amount = averages[category]
                if avg_amount > 0 and current_amount > (2 * avg_amount):
                    anomalies[category] = {
                        'current': current_amount,
                        'average': avg_amount,
                        'increase': ((current_amount / avg_amount) - 1) * 100
                    }

        return anomalies

    except Exception:
        # If historical data not available, no anomalies
        return {}


if __name__ == '__main__':
    sys.exit(main())
