#!/usr/bin/env python3
"""
Personal Finance Skill for Clawdbot
Main entry point with all finance commands
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
    setup_parser = subparsers.add_parser('setup', help='Start bank connection flow')
    setup_parser.add_argument('--country', default='CH', help='Country code (e.g., CH, DE, FR)')
    
    # Balance command
    balance_parser = subparsers.add_parser('balance', help='Show current balances')
    
    # Spending command  
    spending_parser = subparsers.add_parser('spending', help='Show spending summary')
    spending_parser.add_argument('period', nargs='?', default='today', 
                                choices=['today', 'week', 'month'], help='Time period')
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate detailed report')
    report_parser.add_argument('type', nargs='?', default='daily',
                              choices=['daily', 'weekly', 'monthly'], help='Report type')
    
    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Force transaction sync')
    sync_parser.add_argument('--force', action='store_true', help='Ignore rate limits')
    
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
    
    # Accounts command
    accounts_parser = subparsers.add_parser('accounts', help='List connected accounts')

    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare spending between two months')
    compare_parser.add_argument('month1', help='First month (YYYY-MM format)')
    compare_parser.add_argument('month2', nargs='?', help='Second month (YYYY-MM format, defaults to previous month)')

    # Currency command
    currency_parser = subparsers.add_parser('currency', help='Set or show home currency')
    currency_parser.add_argument('code', nargs='?', help='Currency code (e.g., EUR, USD, CHF). Omit to show current.')

    args = parser.parse_args()
    
    if args.command == 'setup':
        return cmd_setup(args.country)
    elif args.command == 'balance':
        return cmd_balance()
    elif args.command == 'spending':
        return cmd_spending(args.period)
    elif args.command == 'report':
        return cmd_report(args.type)
    elif args.command == 'sync':
        return cmd_sync(args.force)
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
    elif args.command == 'accounts':
        return cmd_accounts()
    elif args.command == 'compare':
        return cmd_compare(args.month1, args.month2)
    elif args.command == 'currency':
        return cmd_currency(args.code)
    else:
        parser.print_help()
        return 1

def cmd_setup(country: str) -> int:
    """Interactive onboarding flow"""
    print("=" * 60)
    print("🎉 Welcome to Personal Finance Skill Setup!")
    print("=" * 60)
    print()
    print("This wizard will help you:")
    print("  1️⃣  Get your GoCardless API credentials (free)")
    print("  2️⃣  Connect your bank account (read-only access)")
    print("  3️⃣  Set your preferred currency")
    print()

    # Step 1: Check if credentials already exist
    try:
        from gocardless import GoCardlessClient, KEYCHAIN_AVAILABLE
        from db import get_user_setting

        has_credentials = False
        try:
            client = GoCardlessClient()
            # Try to make a simple API call to verify credentials
            client.list_institutions(country)
            has_credentials = True
            print("✅ GoCardless credentials found and working!")
        except Exception:
            has_credentials = False

        if not has_credentials:
            print("─" * 60)
            print("📋 STEP 1: Get GoCardless API Credentials")
            print("─" * 60)
            print()
            print("GoCardless Bank Account Data provides FREE access to Open Banking.")
            print("You need to create an account and get API credentials.")
            print()
            print("👉 Go to: https://bankaccountdata.gocardless.com/signup")
            print()
            print("After signing up:")
            print("  1. Go to 'User secrets' in the dashboard")
            print("  2. Create a new secret")
            print("  3. Copy your 'secret_id' and 'secret_key'")
            print()

            # Prompt for credentials
            proceed = input("Do you have your credentials ready? (y/n): ").strip().lower()
            if proceed != 'y':
                print()
                print("No problem! Come back when you have your credentials.")
                print("Run '/finance setup' again to continue.")
                return 0

            print()
            secret_id = input("Enter your secret_id: ").strip()
            secret_key = input("Enter your secret_key: ").strip()

            if not secret_id or not secret_key:
                print("❌ Both secret_id and secret_key are required.")
                return 1

            # Save credentials
            from gocardless import setup_credentials_programmatic
            if not setup_credentials_programmatic(secret_id, secret_key):
                print("❌ Failed to save credentials. Please try again.")
                return 1

            print("✅ Credentials saved securely!")
            print()

        # Step 2: Connect bank account
        print("─" * 60)
        print("🏦 STEP 2: Connect Your Bank Account")
        print("─" * 60)
        print()
        print(f"Searching for banks in {country}...")

        from gocardless import setup_bank_connection
        client = GoCardlessClient()
        result = setup_bank_connection(client, country)

        if result['success']:
            print()
            print("✅ Bank connection initiated!")
            print()
            print("👉 Complete authentication at:")
            print(f"   {result['auth_url']}")
            print()
            print("After authenticating with your bank, your account will be")
            print("connected with READ-ONLY access (we cannot make payments).")
            print()

            # Wait for user to complete authentication
            input("Press Enter after you've completed bank authentication...")
            print()

            # Check if accounts were linked
            from gocardless import check_and_update_accounts
            check_and_update_accounts()
        else:
            print(f"⚠️ Bank connection issue: {result.get('error', 'Unknown error')}")
            print("You can try again later with '/finance setup'")

        # Step 3: Set home currency
        print("─" * 60)
        print("💱 STEP 3: Choose Your Home Currency")
        print("─" * 60)
        print()
        print("All amounts will be displayed in your chosen currency.")
        print("Common options: EUR, USD, GBP, CHF, JPY")
        print()

        from currency import get_supported_currencies, get_currency_symbol
        from db import set_home_currency, get_home_currency

        current = get_home_currency()
        currency_input = input(f"Enter currency code [{current}]: ").strip().upper()

        if currency_input:
            supported = get_supported_currencies()
            if currency_input in supported:
                set_home_currency(currency_input)
                symbol = get_currency_symbol(currency_input)
                print(f"✅ Home currency set to: {currency_input} ({symbol})")
            else:
                print(f"⚠️ Unknown currency '{currency_input}', keeping {current}")
        else:
            print(f"✅ Keeping current currency: {current}")

        # Done!
        print()
        print("=" * 60)
        print("🎉 Setup Complete!")
        print("=" * 60)
        print()
        print("You can now use these commands:")
        print("  /finance balance   - View account balances")
        print("  /finance spending  - See spending summary")
        print("  /finance report    - Generate detailed reports")
        print("  /finance sync      - Refresh transaction data")
        print()
        print("💡 Tip: Run '/finance sync' to fetch your latest transactions!")
        return 0

    except ImportError as e:
        print(f"❌ Required module not available: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n\n⚠️ Setup cancelled. Run '/finance setup' to try again.")
        return 1
    except Exception as e:
        print(f"❌ Error during setup: {e}")
        return 1

def cmd_balance() -> int:
    """Show current balances"""
    try:
        from db import get_account_balances
        
        balances = get_account_balances()
        if not balances:
            print("No account balances available. Run 'sync' first.")
            return 1
            
        print("💰 Account Balances")
        print("=" * 40)
        
        total = 0
        for account in balances:
            balance = account['amount']
            currency = account['currency']
            name = account['name'] or account['iban'][:4] + '***'
            
            print(f"• {name}: {balance:,.2f} {currency}")
            if currency == 'CHF':  # Only sum CHF for now
                total += balance
                
        if total > 0:
            print("-" * 40)
            print(f"Total: {total:,.2f} CHF")
            
        return 0
        
    except ImportError:
        print("❌ Database module not available")
        return 1
    except Exception as e:
        print(f"❌ Error fetching balances: {e}")
        return 1

def cmd_spending(period: str) -> int:
    """Show spending summary"""
    try:
        from db import get_spending_by_period, get_category_spending
        from datetime import datetime, timedelta
        
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
            return 1
            
        total_spent = sum(amount for amount in spending.values())
        
        print(f"💸 Spending Summary - {period.title()}")
        print("=" * 40)
        
        # Sort by amount, descending
        for category, amount in sorted(spending.items(), key=lambda x: x[1], reverse=True):
            percentage = (amount / total_spent) * 100 if total_spent > 0 else 0
            emoji = get_category_emoji(category)
            print(f"{emoji} {category.title()}: {amount:,.2f} CHF ({percentage:.0f}%)")
            
        print("-" * 40)
        print(f"Total: {total_spent:,.2f} CHF")
        
        # Simple anomaly detection
        anomalies = detect_spending_anomalies(spending, period)
        if anomalies:
            print("\n🔍 Anomalies Detected:")
            for category, data in anomalies.items():
                print(f"⚠️  {category.title()}: {data['current']:,.2f} CHF "
                      f"(+{data['increase']:.0f}% vs average)")
        
        return 0
        
    except ImportError:
        print("❌ Database module not available") 
        return 1
    except Exception as e:
        print(f"❌ Error fetching spending: {e}")
        return 1

def cmd_report(report_type: str) -> int:
    """Generate detailed report"""
    try:
        import sys
        sys.path.append(str(Path(__file__).parent.parent / 'templates'))
        from reports import generate_report
        from charts import create_spending_pie_chart, cleanup_old_charts

        print(f"📊 Generating {report_type} report...")

        report = generate_report(report_type)
        if not report:
            print(f"❌ Could not generate {report_type} report")
            return 1

        # Print text report
        print(report.text)

        # Generate and save chart
        if report.chart_data:
            chart_path = create_spending_pie_chart(report.chart_data,
                                                 f"{report_type.title()} Spending")
            if chart_path:
                print(f"📈 Chart saved: {chart_path}")

                # In Clawdbot context, this would send via message tool
                # For now, just indicate where to find it
                print(f"💡 View chart: open {chart_path}")

        # Clean up old charts (keep last 7 days)
        cleanup_old_charts(days_to_keep=7)

        return 0

    except ImportError as e:
        print(f"❌ Required module not available: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        return 1

def cmd_sync(force: bool = False) -> int:
    """Force transaction sync"""
    try:
        from gocardless import GoCardlessClient
        from db import store_transactions, get_connected_accounts
        
        print("🔄 Syncing transactions...")
        
        client = GoCardlessClient()
        accounts = get_connected_accounts()
        
        if not accounts:
            print("❌ No connected accounts found. Run 'setup' first.")
            return 1
            
        total_new = 0
        for account in accounts:
            account_id = account['id']
            
            # Check rate limits unless forcing
            if not force:
                from db import check_rate_limit
                if not check_rate_limit(account_id):
                    print(f"⏰ Rate limited for account {account['name'] or account_id[:8]}...")
                    continue
            
            try:
                transactions = client.get_account_transactions(account_id)
                new_count = store_transactions(account_id, transactions)
                total_new += new_count
                
                print(f"✅ {account['name'] or account_id[:8]}... - {new_count} new transactions")
                
            except Exception as e:
                print(f"❌ Failed to sync {account_id[:8]}...: {e}")
                continue
                
        print(f"🎉 Sync complete: {total_new} total new transactions")
        
        # Auto-categorize new transactions
        if total_new > 0:
            from categorize import auto_categorize_recent
            categorized = auto_categorize_recent()
            print(f"🏷️  Auto-categorized {categorized} transactions")
            
        return 0
        
    except ImportError:
        print("❌ Required modules not available")
        return 1
    except Exception as e:
        print(f"❌ Sync error: {e}")
        return 1

def cmd_budget_set(category: str, amount: float) -> int:
    """Set budget for category"""
    try:
        from db import set_category_budget
        
        success = set_category_budget(category.lower(), amount)
        if success:
            print(f"✅ Budget set: {category.title()} = {amount:,.2f} CHF/month")
            return 0
        else:
            print(f"❌ Failed to set budget for {category}")
            return 1
            
    except ImportError:
        print("❌ Database module not available")
        return 1
    except Exception as e:
        print(f"❌ Error setting budget: {e}")
        return 1

def cmd_budget_show() -> int:
    """Show budget status"""
    try:
        from db import get_budget_status
        from datetime import date
        
        # Get current month spending vs budgets
        today = date.today()
        start_date = today.replace(day=1)
        
        budgets = get_budget_status(start_date, today)
        if not budgets:
            print("No budgets set. Use 'budget set <category> <amount>' to create one.")
            return 1
            
        print("🎯 Budget Status - Current Month")
        print("=" * 50)
        
        for budget in budgets:
            category = budget['category']
            limit = budget['monthly_limit'] 
            spent = budget['spent']
            percentage = (spent / limit) * 100 if limit > 0 else 0
            remaining = limit - spent
            
            status_emoji = "🔴" if percentage > 100 else "🟡" if percentage > 80 else "🟢"
            
            print(f"{status_emoji} {category.title()}")
            print(f"   Spent: {spent:,.2f} CHF / {limit:,.2f} CHF ({percentage:.0f}%)")
            print(f"   Remaining: {remaining:,.2f} CHF")
            print()
            
        return 0
        
    except ImportError:
        print("❌ Database module not available")
        return 1
    except Exception as e:
        print(f"❌ Error showing budgets: {e}")
        return 1

def cmd_categorize(transaction_id: str, category: str) -> int:
    """Override transaction category"""
    try:
        from db import set_transaction_category
        
        success = set_transaction_category(transaction_id, category.lower())
        if success:
            print(f"✅ Transaction {transaction_id[:8]}... categorized as '{category.title()}'")
            return 0
        else:
            print(f"❌ Transaction {transaction_id} not found")
            return 1
            
    except ImportError:
        print("❌ Database module not available")
        return 1
    except Exception as e:
        print(f"❌ Error categorizing transaction: {e}")
        return 1

def cmd_currency(code: str = None) -> int:
    """Set or show home currency"""
    try:
        from currency import (
            get_home_currency, set_home_currency, get_currency_symbol,
            get_exchange_rate, get_supported_currencies, format_amount
        )
        from db import set_home_currency as db_set_home

        current = get_home_currency()

        if code is None:
            # Show current currency
            symbol = get_currency_symbol(current)
            print(f"💱 Home Currency: {current} ({symbol})")
            print(f"\nAll amounts will be displayed in {current}.")
            print(f"Use '/finance currency <CODE>' to change (e.g., EUR, USD, CHF)")
            return 0

        code = code.upper()

        # Validate currency code
        supported = get_supported_currencies()
        if code not in supported:
            print(f"❌ Unknown currency: {code}")
            print(f"Supported currencies include: EUR, USD, GBP, CHF, JPY, ...")
            return 1

        # Set new currency
        db_set_home(code)
        symbol = get_currency_symbol(code)

        print(f"✅ Home currency set to: {code} ({symbol})")

        # Show a sample conversion if changing from a different currency
        if code != current:
            rate = get_exchange_rate(current, code)
            if rate:
                print(f"\n💱 Exchange rate: 1 {current} = {rate:.4f} {code}")
                print(f"   Example: {format_amount(100, current)} = {format_amount(100 * rate, code)}")

        return 0

    except ImportError as e:
        print(f"❌ Currency module not available: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error setting currency: {e}")
        return 1


def cmd_accounts() -> int:
    """List connected accounts"""
    try:
        from db import get_connected_accounts
        
        accounts = get_connected_accounts()
        if not accounts:
            print("No connected accounts found.")
            print("Use 'setup' to connect your bank account.")
            return 1
            
        print("🏦 Connected Accounts")
        print("=" * 50)
        
        for account in accounts:
            name = account['name'] or 'Unnamed Account'
            iban = account['iban'] or 'Unknown IBAN'
            bank = account['institution_name'] or 'Unknown Bank'
            status = "✅ Active" if account.get('access_expires_at') else "⚠️ Expired"
            
            print(f"• {name}")
            print(f"  IBAN: {iban}")
            print(f"  Bank: {bank}")
            print(f"  Status: {status}")
            if account.get('last_sync_at'):
                print(f"  Last sync: {account['last_sync_at']}")
            print()
            
        return 0
        
    except ImportError:
        print("❌ Database module not available")
        return 1
    except Exception as e:
        print(f"❌ Error listing accounts: {e}")
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
            print(f"❌ Invalid month format: {month1}. Use YYYY-MM format.")
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
                print(f"❌ Invalid month format: {month2}. Use YYYY-MM format.")
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

        print(f"📊 Spending Comparison")
        print(f"   {start1.strftime('%B %Y')} vs {start2.strftime('%B %Y')}")
        print("=" * 55)

        total1 = sum(spending1.values())
        total2 = sum(spending2.values())

        all_categories = set(spending1.keys()) | set(spending2.keys())

        for category in sorted(all_categories):
            amt1 = spending1.get(category, 0)
            amt2 = spending2.get(category, 0)
            diff = amt1 - amt2
            pct = ((diff / amt2) * 100) if amt2 > 0 else (100 if amt1 > 0 else 0)

            emoji = get_category_emoji(category)
            arrow = "↑" if diff > 0 else "↓" if diff < 0 else "="

            print(f"{emoji} {category.title():<12} {amt1:>8,.0f} vs {amt2:>8,.0f}  {arrow} {diff:+,.0f} ({pct:+.0f}%)")

        print("-" * 55)
        total_diff = total1 - total2
        total_pct = ((total_diff / total2) * 100) if total2 > 0 else 0
        print(f"   {'Total:':<12} {total1:>8,.0f} vs {total2:>8,.0f}  {'+' if total_diff >= 0 else ''}{total_diff:,.0f} ({total_pct:+.0f}%)")

        return 0

    except ImportError:
        print("❌ Database module not available")
        return 1
    except Exception as e:
        print(f"❌ Error comparing months: {e}")
        return 1


def get_category_emoji(category: str) -> str:
    """Get emoji for category"""
    emojis = {
        'groceries': '🛒',
        'dining': '🍽️',
        'transport': '🚃',
        'shopping': '🛍️', 
        'subscriptions': '📺',
        'utilities': '⚡',
        'entertainment': '🎮',
        'health': '🏥',
        'housing': '🏠',
        'other': '📦'
    }
    return emojis.get(category.lower(), '📦')

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