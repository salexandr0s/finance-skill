#!/usr/bin/env python3
"""
Report generation for finance skill
Creates daily, weekly, and monthly reports
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import date, datetime, timedelta
from pathlib import Path
import json

# Add scripts directory to path
import sys
sys.path.append(str(Path(__file__).parent.parent / 'scripts'))

try:
    from db import get_account_balances, get_category_spending, get_spending_by_period, get_budget_status
    from categorize import get_category_stats
except ImportError as e:
    print(f"Warning: Could not import database modules: {e}")

# Currency support (optional - gracefully degrades if not available)
try:
    from currency import (
        get_home_currency, format_amount, format_with_conversion,
        convert_to_home, get_currency_symbol, to_home
    )
    CURRENCY_SUPPORT = True
except ImportError:
    CURRENCY_SUPPORT = False
    def get_home_currency(): return "CHF"
    def format_amount(amt, cur, **kw): return f"{amt:,.2f} {cur}"
    def format_with_conversion(amt, cur, **kw): return f"{amt:,.2f} {cur}"
    def to_home(amt, cur): return amt
    def get_currency_symbol(cur): return cur

@dataclass
class Report:
    """Report data structure"""
    type: str  # daily, weekly, monthly
    period_start: date
    period_end: date
    text: str
    chart_data: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = None

def generate_report(report_type: str = 'daily') -> Optional[Report]:
    """Generate report of specified type"""
    if report_type == 'daily':
        return generate_daily_report()
    elif report_type == 'weekly':
        return generate_weekly_report()
    elif report_type == 'monthly':
        return generate_monthly_report()
    else:
        return None

def generate_daily_report(target_date: date = None) -> Optional[Report]:
    """Generate daily finance brief"""
    if target_date is None:
        target_date = date.today()

    yesterday = target_date - timedelta(days=1)
    home_currency = get_home_currency()
    home_symbol = get_currency_symbol(home_currency)

    try:
        # Get account balances
        balances = get_account_balances()

        # Get yesterday's spending by category
        yesterday_spending = get_category_spending(yesterday, yesterday)

        # Calculate totals (convert all to home currency)
        total_balance_home = 0.0
        for b in balances:
            total_balance_home += to_home(b['amount'], b['currency'])

        total_spent_yesterday = sum(yesterday_spending.values())

        # Format report text
        text_lines = [
            f"🌅 **Daily Finance Brief** — {target_date.strftime('%A, %B %d, %Y')}",
            "",
            "💰 **Account Balances**"
        ]

        if balances:
            for balance in balances[:5]:  # Show top 5 accounts
                iban = balance.get('iban') or 'Unknown'
                name = balance['name'] or f"Account {iban[:4]}***"
                amount = balance['amount']
                currency = balance['currency']
                # Show with conversion if different from home currency
                amount_str = format_with_conversion(amount, currency)
                text_lines.append(f"• {name}: {amount_str}")

            if len(balances) > 5:
                text_lines.append(f"• ... and {len(balances) - 5} more accounts")

            if total_balance_home > 0:
                text_lines.append(f"**Total: {format_amount(total_balance_home, home_currency)}**")
        else:
            text_lines.append("• No balance data available")
        
        text_lines.extend([
            "",
            f"📊 **Yesterday** ({yesterday.strftime('%A, %B %d')})"
        ])
        
        if yesterday_spending:
            text_lines.append(f"Spent: **{total_spent_yesterday:,.2f} CHF** ({len(yesterday_spending)} categories)")
            text_lines.append("")
            
            # Show top spending categories
            sorted_spending = sorted(yesterday_spending.items(), key=lambda x: x[1], reverse=True)
            for category, amount in sorted_spending[:8]:  # Top 8 categories
                emoji = get_category_emoji(category)
                text_lines.append(f"{emoji} {category.title()}: {amount:,.2f} CHF")
        else:
            text_lines.append("No spending recorded yesterday")
        
        # Add comparison to typical day (if we have historical data)
        try:
            from db import get_historical_category_averages
            historical_averages = get_historical_category_averages('today', 4)  # Last 4 weeks
            
            if historical_averages:
                total_avg = sum(historical_averages.values())
                if total_avg > 0:
                    difference = total_spent_yesterday - total_avg
                    percent_diff = (difference / total_avg) * 100
                    
                    text_lines.extend([
                        "",
                        f"📈 **vs. Typical {yesterday.strftime('%A')}:**"
                    ])
                    
                    if abs(percent_diff) > 20:
                        status = "⬆️ Higher" if difference > 0 else "⬇️ Lower"
                        text_lines.append(f"{status} than usual ({difference:+.2f} CHF, {percent_diff:+.0f}%)")
                    else:
                        text_lines.append("✅ Normal spending pattern")
                        
        except Exception:
            pass  # Historical comparison optional
        
        # Create report
        report = Report(
            type='daily',
            period_start=yesterday,
            period_end=yesterday,
            text='\n'.join(text_lines),
            chart_data=yesterday_spending if yesterday_spending else None,
            metadata={'total_spent': total_spent_yesterday, 'total_balance': total_balance}
        )
        
        return report
        
    except Exception as e:
        print(f"Error generating daily report: {e}")
        return None

def generate_weekly_report(target_date: date = None) -> Optional[Report]:
    """Generate weekly finance summary"""
    if target_date is None:
        target_date = date.today()
        
    # Get current week (Monday to Sunday)
    days_since_monday = target_date.weekday()
    week_start = target_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    
    # Previous week for comparison
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = week_start - timedelta(days=1)
    
    try:
        # Get weekly spending
        current_spending = get_category_spending(week_start, week_end)
        previous_spending = get_category_spending(prev_week_start, prev_week_end)
        
        # Get daily breakdown
        daily_spending = get_spending_by_period('day', 7)
        
        # Get budget status
        budgets = get_budget_status(week_start.replace(day=1), week_end)
        
        # Calculate totals
        total_current = sum(current_spending.values())
        total_previous = sum(previous_spending.values())
        week_change = total_current - total_previous
        week_change_pct = (week_change / total_previous * 100) if total_previous > 0 else 0
        
        # Format report text
        week_num = week_start.isocalendar()[1]
        year = week_start.year
        
        text_lines = [
            f"📊 **Weekly Finance Summary** — Week {week_num}, {year}",
            f"*{week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}*",
            "",
            f"💸 **Total Spent: {total_current:,.2f} CHF**"
        ]
        
        # Week-over-week comparison
        if total_previous > 0:
            change_emoji = "📈" if week_change > 0 else "📉"
            direction = "↑" if week_change > 0 else "↓"
            text_lines.append(f"   vs last week: {week_change:+.0f} CHF ({direction}{abs(week_change_pct):.0f}%)")
        
        text_lines.extend([
            "",
            "📂 **By Category:**"
        ])
        
        # Category breakdown
        if current_spending:
            sorted_spending = sorted(current_spending.items(), key=lambda x: x[1], reverse=True)
            for category, amount in sorted_spending:
                percentage = (amount / total_current * 100) if total_current > 0 else 0
                emoji = get_category_emoji(category)
                
                # Progress bar (visual representation)
                bar_length = min(10, int(percentage / 5))  # 5% per bar segment
                bar = "█" * bar_length + "░" * (10 - bar_length)
                
                text_lines.append(f"{emoji} {category.title():<12} {amount:>8,.0f} CHF {bar} {percentage:>3.0f}%")
        
        # Budget status (if any budgets set)
        if budgets:
            text_lines.extend([
                "",
                "🎯 **Budget Status:**"
            ])
            
            for budget in budgets[:5]:  # Show top 5 budgets
                category = budget['category']
                spent = budget['spent']
                limit = budget['monthly_limit']
                percentage = (spent / limit * 100) if limit > 0 else 0
                
                if percentage > 100:
                    status = "🔴 Over budget"
                elif percentage > 80:
                    status = "🟡 Approaching limit"
                else:
                    status = "🟢 On track"
                    
                text_lines.append(f"{category.title()}: {spent:.0f}/{limit:.0f} CHF ({percentage:.0f}%) {status}")
        
        # Daily breakdown summary
        if daily_spending and len(daily_spending) > 1:
            text_lines.extend([
                "",
                "📅 **This Week:**"
            ])
            
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            for i, (day_str, amount) in enumerate(daily_spending[-7:]):  # Last 7 days
                day_name = day_names[i % 7] if i < 7 else day_str
                text_lines.append(f"{day_name}: {amount:,.0f} CHF")
        
        # Create report
        report = Report(
            type='weekly',
            period_start=week_start,
            period_end=week_end,
            text='\n'.join(text_lines),
            chart_data=current_spending if current_spending else None,
            metadata={
                'total_current': total_current,
                'total_previous': total_previous,
                'change': week_change,
                'change_percent': week_change_pct,
                'budgets': budgets
            }
        )
        
        return report
        
    except Exception as e:
        print(f"Error generating weekly report: {e}")
        return None

def generate_monthly_report(target_date: date = None) -> Optional[Report]:
    """Generate monthly finance deep-dive"""
    if target_date is None:
        target_date = date.today()
    
    # Current month
    month_start = target_date.replace(day=1)
    if target_date.month == 12:
        month_end = date(target_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(target_date.year, target_date.month + 1, 1) - timedelta(days=1)
    
    # Previous month for comparison
    if month_start.month == 1:
        prev_month_start = date(month_start.year - 1, 12, 1)
        prev_month_end = date(month_start.year, 1, 1) - timedelta(days=1)
    else:
        prev_month_start = date(month_start.year, month_start.month - 1, 1)
        prev_month_end = month_start - timedelta(days=1)
    
    try:
        # Get spending data
        current_spending = get_category_spending(month_start, month_end)
        previous_spending = get_category_spending(prev_month_start, prev_month_end)
        
        # Get account balances
        balances = get_account_balances()
        total_balance = sum(b['amount'] for b in balances if b['currency'] == 'CHF')
        
        # Calculate totals
        total_expenses = sum(current_spending.values())
        total_prev_expenses = sum(previous_spending.values())
        
        # Estimate income (simplified)
        from db import get_db
        with get_db() as conn:
            cursor = conn.execute("""
                SELECT SUM(amount) as total_income
                FROM transactions
                WHERE amount > 0 
                AND booking_date >= ? 
                AND booking_date <= ?
                AND amount > 100  -- Filter out small transfers
            """, (month_start.isoformat(), month_end.isoformat()))
            
            result = cursor.fetchone()
            estimated_income = result['total_income'] if result and result['total_income'] else 0
        
        # Net savings
        net_savings = estimated_income - total_expenses
        savings_rate = (net_savings / estimated_income * 100) if estimated_income > 0 else 0
        
        # Format report text
        text_lines = [
            f"📈 **Monthly Finance Report** — {month_start.strftime('%B %Y')}",
            "",
            "💰 **Summary**"
        ]
        
        if estimated_income > 0:
            text_lines.extend([
                f"Income:      {estimated_income:>10,.0f} CHF",
                f"Expenses:    {total_expenses:>10,.0f} CHF",
                f"Net:         {net_savings:>+10,.0f} CHF ({savings_rate:+.0f}%)"
            ])
        else:
            text_lines.append(f"Total Expenses: {total_expenses:,.0f} CHF")
            
        text_lines.extend([
            f"Current Balance: {total_balance:>6,.0f} CHF",
            "",
            "📊 **Top Categories:**"
        ])
        
        # Top spending categories
        if current_spending:
            sorted_spending = sorted(current_spending.items(), key=lambda x: x[1], reverse=True)
            
            for i, (category, amount) in enumerate(sorted_spending[:10], 1):
                percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
                emoji = get_category_emoji(category)
                text_lines.append(f"{i:2d}. {emoji} {category.title():<15} {amount:>8,.0f} CHF ({percentage:>3.0f}%)")
        
        # Month-over-month comparison
        if previous_spending:
            text_lines.extend([
                "",
                f"📈 **vs. {prev_month_start.strftime('%B')}:**"
            ])
            
            # Compare top categories
            for category in sorted_spending[:5]:  # Top 5
                category_name = category[0]
                current_amount = category[1]
                prev_amount = previous_spending.get(category_name, 0)
                
                if prev_amount > 0:
                    change = current_amount - prev_amount
                    change_pct = (change / prev_amount * 100)
                    
                    direction = "+" if change > 0 else ""
                    emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                    
                    text_lines.append(f"• {category_name.title()}: {direction}{change:,.0f} CHF ({change_pct:+.0f}%) {emoji}")
        
        # Insights and patterns
        text_lines.extend([
            "",
            "🔍 **Insights:**"
        ])
        
        # Generate insights based on data
        insights = []
        
        # Spending pattern insights
        if len(current_spending) > 0:
            top_category = max(current_spending.items(), key=lambda x: x[1])
            insights.append(f"• Your biggest expense category is {top_category[0]} ({top_category[1]:,.0f} CHF)")
        
        # Savings insights
        if savings_rate > 20:
            insights.append(f"• Excellent savings rate of {savings_rate:.0f}%!")
        elif savings_rate > 10:
            insights.append(f"• Good savings rate of {savings_rate:.0f}%")
        elif savings_rate > 0:
            insights.append(f"• Positive savings of {savings_rate:.0f}%")
        elif savings_rate < 0:
            insights.append(f"• ⚠️ Spending exceeded income by {abs(savings_rate):.0f}%")
        
        # Comparison insights
        if total_prev_expenses > 0:
            expense_change = total_expenses - total_prev_expenses
            if abs(expense_change) > total_prev_expenses * 0.1:  # >10% change
                direction = "increased" if expense_change > 0 else "decreased"
                insights.append(f"• Monthly spending {direction} by {abs(expense_change):,.0f} CHF vs last month")
        
        # Add insights to report
        if insights:
            text_lines.extend(insights)
        else:
            text_lines.append("• No significant patterns detected this month")

        # Add crypto holdings section
        crypto_lines, crypto_usd, crypto_home = get_crypto_section()
        if crypto_lines:
            text_lines.extend(crypto_lines)

        # Calculate total assets (bank + crypto)
        total_assets = total_balance + crypto_home

        # Add total assets summary if we have crypto
        if crypto_home > 0:
            text_lines.extend([
                "",
                "💎 **Total Assets:**",
                f"Bank Accounts: {total_balance:>10,.0f} CHF",
                f"Crypto:        {crypto_home:>10,.0f} CHF",
                f"**Total:       {total_assets:>10,.0f} CHF**"
            ])

        # Create report
        report = Report(
            type='monthly',
            period_start=month_start,
            period_end=month_end,
            text='\n'.join(text_lines),
            chart_data=current_spending if current_spending else None,
            metadata={
                'total_expenses': total_expenses,
                'estimated_income': estimated_income,
                'net_savings': net_savings,
                'savings_rate': savings_rate,
                'total_balance': total_balance,
                'previous_expenses': total_prev_expenses,
                'crypto_total_usd': crypto_usd,
                'crypto_total_home': crypto_home,
                'total_assets': total_assets
            }
        )

        return report
        
    except Exception as e:
        print(f"Error generating monthly report: {e}")
        return None

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
        'transfers': '↔️',
        'income': '💰',
        'other': '📦'
    }
    return emojis.get(category.lower(), '📦')


def get_crypto_section() -> tuple:
    """
    Generate crypto holdings section for reports.

    Returns:
        Tuple of (text_lines: List[str], total_usd: float, total_home: float)
    """
    try:
        from db import get_wallets, get_latest_wallet_snapshot
        from crypto import format_crypto_value, sync_all_wallets

        wallets = get_wallets()
        if not wallets:
            return [], 0.0, 0.0

        # Sync wallets to get latest values
        try:
            sync_all_wallets(force=False)  # Use cached if recent
        except Exception:
            pass  # Continue with cached data if sync fails

        lines = [
            "",
            "🪙 **Crypto Holdings:**"
        ]

        total_usd = 0.0
        for wallet in wallets:
            snapshot = get_latest_wallet_snapshot(wallet['id'])
            if snapshot:
                value_usd = snapshot['total_value_usd']
                total_usd += value_usd

                label = wallet['label'] or f"{wallet['blockchain'].title()} Wallet"
                value_str = format_crypto_value(value_usd)
                lines.append(f"• {label}: {value_str}")

        if total_usd > 0:
            total_str = format_crypto_value(total_usd)
            lines.append(f"**Total Crypto: {total_str}**")

        # Convert total to home currency
        total_home = total_usd
        try:
            from currency import convert
            home_currency = get_home_currency()
            if home_currency.upper() != 'USD':
                result = convert(total_usd, 'USD', home_currency)
                if result:
                    total_home = result[0]
        except Exception:
            pass

        return lines, total_usd, total_home

    except ImportError:
        return [], 0.0, 0.0
    except Exception as e:
        print(f"Warning: Could not get crypto data: {e}")
        return [], 0.0, 0.0

def save_report(report: Report, output_dir: Path = None) -> str:
    """Save report to file"""
    if output_dir is None:
        output_dir = Path.home() / '.config' / 'clawdbot-finance' / 'reports'
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    date_str = report.period_start.strftime('%Y-%m-%d')
    if report.type == 'weekly':
        week_num = report.period_start.isocalendar()[1]
        filename = f"weekly-{report.period_start.year}-W{week_num:02d}.md"
    elif report.type == 'monthly':
        filename = f"monthly-{report.period_start.strftime('%Y-%m')}.md"
    else:  # daily
        filename = f"daily-{date_str}.md"
    
    filepath = output_dir / filename
    
    # Create report content with metadata
    content = [
        f"# {report.type.title()} Finance Report",
        f"**Period:** {report.period_start} to {report.period_end}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        report.text
    ]
    
    # Add metadata
    if report.metadata:
        content.extend([
            "",
            "---",
            "",
            "## Metadata",
            "```json",
            json.dumps(report.metadata, indent=2, default=str),
            "```"
        ])
    
    with open(filepath, 'w') as f:
        f.write('\n'.join(content))
    
    return str(filepath)

def get_report_history(report_type: str = None, limit: int = 10) -> List[Dict]:
    """Get list of previously generated reports"""
    reports_dir = Path.home() / '.config' / 'clawdbot-finance' / 'reports'
    
    if not reports_dir.exists():
        return []
    
    reports = []
    pattern = f"{report_type}-*.md" if report_type else "*.md"
    
    for report_file in reports_dir.glob(pattern):
        try:
            # Extract date from filename
            parts = report_file.stem.split('-')
            if len(parts) >= 2:
                report_date = '-'.join(parts[1:])
                reports.append({
                    'type': parts[0],
                    'date': report_date,
                    'filepath': str(report_file),
                    'created': datetime.fromtimestamp(report_file.stat().st_mtime)
                })
        except Exception:
            continue
    
    # Sort by creation date, newest first
    reports.sort(key=lambda x: x['created'], reverse=True)
    
    return reports[:limit]

if __name__ == '__main__':
    # Test report generation
    print("Testing report generation...")
    
    daily_report = generate_daily_report()
    if daily_report:
        print("✅ Daily report generated")
        print(daily_report.text[:200] + "...")
    else:
        print("❌ Failed to generate daily report")
    
    weekly_report = generate_weekly_report()
    if weekly_report:
        print("✅ Weekly report generated")
    else:
        print("❌ Failed to generate weekly report")
        
    monthly_report = generate_monthly_report()
    if monthly_report:
        print("✅ Monthly report generated")
    else:
        print("❌ Failed to generate monthly report")