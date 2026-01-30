#!/usr/bin/env python3
"""
Subscription management for finance skill.
Combines manual subscription tracking with auto-detection from transactions.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Add database module
import sys
sys.path.insert(0, str(Path(__file__).parent))

from db import (
    get_db, get_subscriptions, get_subscription_totals,
    add_subscription, update_subscription, delete_subscription,
    get_subscription_by_merchant, get_subscription_by_id, get_upcoming_renewals
)

# Known subscription services (merchant patterns -> friendly name, category)
KNOWN_SUBSCRIPTIONS = {
    # Streaming & Entertainment
    'netflix': ('Netflix', 'streaming'),
    'spotify': ('Spotify', 'streaming'),
    'apple.com/bill': ('Apple Services', 'streaming'),
    'apple music': ('Apple Music', 'streaming'),
    'disney plus': ('Disney+', 'streaming'),
    'disney+': ('Disney+', 'streaming'),
    'hbo max': ('HBO Max', 'streaming'),
    'amazon prime': ('Amazon Prime', 'streaming'),
    'prime video': ('Amazon Prime Video', 'streaming'),
    'youtube premium': ('YouTube Premium', 'streaming'),
    'youtube music': ('YouTube Music', 'streaming'),
    'dazn': ('DAZN', 'streaming'),
    'crunchyroll': ('Crunchyroll', 'streaming'),
    'paramount+': ('Paramount+', 'streaming'),
    'peacock': ('Peacock', 'streaming'),
    'hulu': ('Hulu', 'streaming'),
    'audible': ('Audible', 'streaming'),
    'kindle unlimited': ('Kindle Unlimited', 'streaming'),

    # AI & Productivity
    'anthropic': ('Claude (Anthropic)', 'ai_productivity'),
    'claude': ('Claude (Anthropic)', 'ai_productivity'),
    'openai': ('OpenAI / ChatGPT', 'ai_productivity'),
    'chatgpt': ('OpenAI / ChatGPT', 'ai_productivity'),
    'midjourney': ('Midjourney', 'ai_productivity'),
    'github': ('GitHub', 'ai_productivity'),
    'copilot': ('GitHub Copilot', 'ai_productivity'),
    'notion': ('Notion', 'ai_productivity'),
    '1password': ('1Password', 'ai_productivity'),
    'lastpass': ('LastPass', 'ai_productivity'),
    'bitwarden': ('Bitwarden', 'ai_productivity'),
    'dropbox': ('Dropbox', 'cloud'),
    'google storage': ('Google One', 'cloud'),
    'google one': ('Google One', 'cloud'),
    'icloud': ('iCloud+', 'cloud'),
    'microsoft 365': ('Microsoft 365', 'ai_productivity'),
    'office 365': ('Microsoft 365', 'ai_productivity'),
    'adobe': ('Adobe Creative Cloud', 'ai_productivity'),
    'creative cloud': ('Adobe Creative Cloud', 'ai_productivity'),
    'canva': ('Canva', 'ai_productivity'),
    'figma': ('Figma', 'ai_productivity'),
    'slack': ('Slack', 'ai_productivity'),
    'zoom': ('Zoom', 'ai_productivity'),
    'linear': ('Linear', 'ai_productivity'),
    'grammarly': ('Grammarly', 'ai_productivity'),

    # Gaming
    'playstation': ('PlayStation Plus', 'gaming'),
    'ps plus': ('PlayStation Plus', 'gaming'),
    'xbox': ('Xbox Game Pass', 'gaming'),
    'game pass': ('Xbox Game Pass', 'gaming'),
    'nintendo': ('Nintendo Online', 'gaming'),
    'ea play': ('EA Play', 'gaming'),
    'steam': ('Steam', 'gaming'),
    'epic games': ('Epic Games', 'gaming'),

    # News & Reading
    'nyt': ('New York Times', 'news'),
    'new york times': ('New York Times', 'news'),
    'washington post': ('Washington Post', 'news'),
    'economist': ('The Economist', 'news'),
    'medium': ('Medium', 'news'),
    'substack': ('Substack', 'news'),
    'financial times': ('Financial Times', 'news'),
    'wall street journal': ('Wall Street Journal', 'news'),
    'wsj': ('Wall Street Journal', 'news'),
    'bloomberg': ('Bloomberg', 'news'),

    # Health & Fitness
    'strava': ('Strava', 'fitness'),
    'fitbit': ('Fitbit Premium', 'fitness'),
    'headspace': ('Headspace', 'fitness'),
    'calm': ('Calm', 'fitness'),
    'peloton': ('Peloton', 'fitness'),
    'myfitnesspal': ('MyFitnessPal', 'fitness'),
    'noom': ('Noom', 'fitness'),

    # VPN & Security
    'nordvpn': ('NordVPN', 'security'),
    'expressvpn': ('ExpressVPN', 'security'),
    'surfshark': ('Surfshark', 'security'),
    'protonvpn': ('ProtonVPN', 'security'),
    'proton': ('Proton', 'security'),
    'mullvad': ('Mullvad VPN', 'security'),

    # Learning
    'duolingo': ('Duolingo', 'learning'),
    'skillshare': ('Skillshare', 'learning'),
    'masterclass': ('MasterClass', 'learning'),
    'coursera': ('Coursera', 'learning'),
    'udemy': ('Udemy', 'learning'),
    'linkedin learning': ('LinkedIn Learning', 'learning'),
    'brilliant': ('Brilliant', 'learning'),

    # Finance
    'ynab': ('YNAB', 'finance'),
    'revolut': ('Revolut Premium', 'finance'),
    'n26': ('N26 Premium', 'finance'),
    'wise': ('Wise', 'finance'),

    # Other
    'patreon': ('Patreon', 'other'),
    'twitch': ('Twitch', 'other'),
    'discord': ('Discord Nitro', 'other'),
}

# Category display names
CATEGORY_LABELS = {
    'streaming': 'Streaming & Entertainment',
    'ai_productivity': 'AI & Productivity',
    'cloud': 'Cloud Storage',
    'gaming': 'Gaming',
    'news': 'News & Reading',
    'fitness': 'Health & Fitness',
    'security': 'VPN & Security',
    'learning': 'Learning',
    'finance': 'Finance',
    'other': 'Other',
    'subscriptions': 'Other',
}


@dataclass
class DetectedSubscription:
    """Auto-detected subscription from transaction history"""
    name: str
    merchant_pattern: str
    amount: float
    currency: str
    frequency: str
    last_charge: date
    charge_count: int
    confidence: float
    category: str


def detect_subscriptions_from_transactions(months_to_analyze: int = 6) -> List[DetectedSubscription]:
    """
    Auto-detect potential subscriptions from transaction history.

    Args:
        months_to_analyze: Number of months of history to analyze

    Returns:
        List of detected subscriptions (suggestions, not yet added)
    """
    cutoff_date = (date.today() - timedelta(days=months_to_analyze * 30)).isoformat()

    with get_db() as conn:
        cursor = conn.execute("""
            SELECT
                id, booking_date, amount, currency,
                creditor_name, description, category
            FROM transactions
            WHERE amount < 0
            AND booking_date >= ?
            ORDER BY booking_date
        """, (cutoff_date,))

        transactions = [dict(row) for row in cursor.fetchall()]

    if not transactions:
        return []

    # Group transactions by normalized merchant
    merchant_transactions = defaultdict(list)

    for txn in transactions:
        merchant = _normalize_merchant(txn)
        if merchant:
            merchant_transactions[merchant].append(txn)

    # Analyze each merchant for subscription patterns
    detected = []

    for merchant, txns in merchant_transactions.items():
        result = _analyze_merchant_pattern(merchant, txns)
        if result:
            # Skip if already tracked in subscriptions table
            existing = get_subscription_by_merchant(merchant)
            if not existing:
                detected.append(result)

    # Sort by amount (highest first)
    detected.sort(key=lambda s: s.amount, reverse=True)

    return detected


def _normalize_merchant(txn: Dict) -> Optional[str]:
    """Normalize merchant name from transaction."""
    text = txn.get('creditor_name') or txn.get('description') or ''
    text = text.lower().strip()

    if not text:
        return None

    # Remove common prefixes/suffixes
    text = re.sub(r'^(payment to|direct debit|recurring|subscription)\s*', '', text)
    text = re.sub(r'\s*(gmbh|ltd|inc|llc|ag|sa|bv)\.?$', '', text)
    text = re.sub(r'\d{2}[./]\d{2}[./]\d{2,4}', '', text)
    text = re.sub(r'ref[:\s]*\d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()

    # Match against known subscriptions
    for pattern in KNOWN_SUBSCRIPTIONS:
        if pattern in text:
            return pattern

    return text[:50] if len(text) > 3 else None


def _analyze_merchant_pattern(merchant: str, transactions: List[Dict]) -> Optional[DetectedSubscription]:
    """Analyze transactions to detect subscription pattern."""
    if len(transactions) < 2:
        return None

    transactions.sort(key=lambda t: t['booking_date'])

    amounts = [abs(t['amount']) for t in transactions]
    currencies = [t['currency'] for t in transactions]
    dates = [date.fromisoformat(t['booking_date']) for t in transactions]

    # Check amount consistency
    avg_amount = sum(amounts) / len(amounts)
    if avg_amount == 0:
        return None

    amount_variance = max(abs(a - avg_amount) / avg_amount for a in amounts)
    if amount_variance > 0.15:
        return None

    # Check frequency
    intervals = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
    if not intervals:
        return None

    avg_interval = sum(intervals) / len(intervals)

    frequency = None
    confidence = 0.0

    if 25 <= avg_interval <= 35:
        frequency = 'monthly'
        confidence = 0.9
    elif 350 <= avg_interval <= 380:
        frequency = 'yearly'
        confidence = 0.85
    elif 6 <= avg_interval <= 8:
        frequency = 'weekly'
        confidence = 0.8
    elif 85 <= avg_interval <= 95:
        frequency = 'quarterly'
        confidence = 0.85
    elif len(transactions) >= 3 and 20 <= avg_interval <= 40:
        frequency = 'monthly'
        confidence = 0.6
    else:
        return None

    if len(transactions) >= 6:
        confidence = min(1.0, confidence + 0.1)
    elif len(transactions) == 2:
        confidence = max(0.4, confidence - 0.2)

    # Get name and category
    known = KNOWN_SUBSCRIPTIONS.get(merchant)
    if known:
        name, category = known
    else:
        name = merchant.title()
        category = 'other'

    return DetectedSubscription(
        name=name,
        merchant_pattern=merchant,
        amount=round(avg_amount, 2),
        currency=currencies[-1],
        frequency=frequency,
        last_charge=dates[-1],
        charge_count=len(transactions),
        confidence=confidence,
        category=category
    )


def get_subscription_summary() -> Dict:
    """
    Get subscription summary for reports.
    Uses stored subscriptions (not auto-detected).

    Returns:
        Dictionary with totals and subscription list
    """
    return get_subscription_totals()


def format_subscription_report(summary: Dict) -> List[str]:
    """
    Format subscription summary as text lines for reports.

    Returns:
        List of formatted text lines
    """
    lines = []
    currency = summary.get('currency', 'EUR')

    subscriptions = summary.get('subscriptions', [])
    if not subscriptions:
        lines.append("")
        lines.append("**Subscriptions:**")
        lines.append("No subscriptions tracked yet.")
        lines.append("Use `subscriptions add` to add your subscriptions.")
        return lines

    # Header with totals
    lines.extend([
        "",
        "**Subscriptions:**",
        f"Monthly Total: **{summary['monthly_total']:,.2f} {currency}**",
        f"Yearly Total: **{summary['yearly_total']:,.2f} {currency}**",
        ""
    ])

    # Group by category
    by_category = summary.get('by_category', {})

    for category, subs in sorted(by_category.items()):
        if not subs:
            continue

        cat_label = CATEGORY_LABELS.get(category, category.title())
        lines.append(f"**{cat_label}:**")

        for sub in sorted(subs, key=lambda s: s['amount'], reverse=True):
            cycle = sub.get('billing_cycle', 'monthly')
            amount = sub['amount']

            # Format frequency indicator
            freq_indicator = {
                'monthly': '/mo',
                'yearly': '/yr',
                'weekly': '/wk',
                'quarterly': '/qtr'
            }.get(cycle, '')

            # Format amount with monthly equivalent for non-monthly
            if cycle == 'yearly':
                monthly_equiv = amount / 12
                amount_str = f"{amount:,.2f} {sub['currency']}{freq_indicator} (~{monthly_equiv:,.2f}/mo)"
            elif cycle == 'quarterly':
                monthly_equiv = amount / 3
                amount_str = f"{amount:,.2f} {sub['currency']}{freq_indicator} (~{monthly_equiv:,.2f}/mo)"
            else:
                amount_str = f"{amount:,.2f} {sub['currency']}{freq_indicator}"

            # Status indicator
            status = sub.get('status', 'active')
            status_indicator = "" if status == 'active' else f" ({status})"

            lines.append(f"  {sub['name']}: {amount_str}{status_indicator}")

        lines.append("")

    # Show upcoming renewals
    upcoming = get_upcoming_renewals(days=7)
    if upcoming:
        lines.append("**Upcoming Renewals (7 days):**")
        for sub in upcoming:
            lines.append(f"  {sub['name']}: {sub['next_billing_date']}")
        lines.append("")

    return lines


def format_detected_subscriptions(detected: List[DetectedSubscription]) -> List[str]:
    """Format detected subscriptions as suggestions."""
    if not detected:
        return ["No additional subscriptions detected from your transactions."]

    lines = [
        "",
        "**Detected Subscriptions (not yet tracked):**",
        ""
    ]

    for i, sub in enumerate(detected, 1):
        conf_pct = int(sub.confidence * 100)
        lines.append(
            f"{i}. {sub.name}: {sub.amount:,.2f} {sub.currency} ({sub.frequency}) "
            f"[{conf_pct}% confidence]"
        )

    lines.extend([
        "",
        "Use `subscriptions add <name> <amount> <cycle>` to track a subscription.",
        "Or `subscriptions detect --add` to add all detected subscriptions."
    ])

    return lines


def cmd_list_subscriptions(include_cancelled: bool = False) -> None:
    """List all tracked subscriptions."""
    summary = get_subscription_summary()
    lines = format_subscription_report(summary)

    for line in lines:
        print(line)


def cmd_add_subscription(
    name: str,
    amount: float,
    cycle: str = 'monthly',
    currency: str = 'EUR',
    category: str = None,
    next_billing: str = None,
    website: str = None,
    notes: str = None
) -> bool:
    """Add a new subscription."""
    # Validate amount
    if amount <= 0:
        print(f"Error: Amount must be positive (got {amount})")
        return False

    # Validate billing cycle
    valid_cycles = {'weekly', 'monthly', 'quarterly', 'yearly'}
    if cycle not in valid_cycles:
        print(f"Error: Invalid billing cycle '{cycle}'. Use: {', '.join(valid_cycles)}")
        return False

    # Auto-detect category from name
    if not category:
        name_lower = name.lower()
        for pattern, (_, cat) in KNOWN_SUBSCRIPTIONS.items():
            if pattern in name_lower:
                category = cat
                break
        if not category:
            category = 'other'

    # Auto-detect merchant pattern
    merchant_pattern = None
    name_lower = name.lower()
    for pattern in KNOWN_SUBSCRIPTIONS:
        if pattern in name_lower:
            merchant_pattern = pattern
            break

    sub_id = add_subscription(
        name=name,
        amount=amount,
        currency=currency,
        billing_cycle=cycle,
        category=category,
        next_billing_date=next_billing,
        merchant_pattern=merchant_pattern,
        website=website,
        notes=notes
    )

    if sub_id > 0:
        print(f"Added subscription: {name} ({amount} {currency}/{cycle})")
        return True
    else:
        print(f"Failed to add subscription: {name}")
        return False


def cmd_remove_subscription(subscription_id: int) -> bool:
    """Remove a subscription."""
    sub = get_subscription_by_id(subscription_id)
    if not sub:
        print(f"Subscription #{subscription_id} not found")
        return False

    if delete_subscription(subscription_id):
        print(f"Removed subscription: {sub['name']}")
        return True
    else:
        print(f"Failed to remove subscription #{subscription_id}")
        return False


def cmd_pause_subscription(subscription_id: int) -> bool:
    """Pause a subscription."""
    sub = get_subscription_by_id(subscription_id)
    if not sub:
        print(f"Subscription #{subscription_id} not found")
        return False

    if update_subscription(subscription_id, status='paused'):
        print(f"Paused subscription: {sub['name']}")
        return True
    return False


def cmd_resume_subscription(subscription_id: int) -> bool:
    """Resume a paused subscription."""
    sub = get_subscription_by_id(subscription_id)
    if not sub:
        print(f"Subscription #{subscription_id} not found")
        return False

    if update_subscription(subscription_id, status='active'):
        print(f"Resumed subscription: {sub['name']}")
        return True
    return False


def cmd_detect_subscriptions(auto_add: bool = False) -> None:
    """Detect subscriptions from transaction history."""
    print("Analyzing transaction history...")
    detected = detect_subscriptions_from_transactions()

    if not detected:
        print("No new subscriptions detected.")
        return

    if auto_add:
        added = 0
        for sub in detected:
            if sub.confidence >= 0.7:
                success = cmd_add_subscription(
                    name=sub.name,
                    amount=sub.amount,
                    cycle=sub.frequency,
                    currency=sub.currency,
                    category=sub.category
                )
                if success:
                    added += 1
        print(f"\nAdded {added} subscriptions from detection.")
    else:
        lines = format_detected_subscriptions(detected)
        for line in lines:
            print(line)


def get_subscriptions_text() -> str:
    """Get formatted subscription text for direct display."""
    summary = get_subscription_summary()
    lines = format_subscription_report(summary)
    return '\n'.join(lines)


# CLI entry point
if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        cmd_list_subscriptions()
    elif sys.argv[1] == 'detect':
        auto_add = '--add' in sys.argv
        cmd_detect_subscriptions(auto_add)
    elif sys.argv[1] == 'add' and len(sys.argv) >= 4:
        name = sys.argv[2]
        amount = float(sys.argv[3])
        cycle = sys.argv[4] if len(sys.argv) > 4 else 'monthly'
        cmd_add_subscription(name, amount, cycle)
    elif sys.argv[1] == 'remove' and len(sys.argv) >= 3:
        sub_id = int(sys.argv[2])
        cmd_remove_subscription(sub_id)
    else:
        print("Usage:")
        print("  python subscriptions.py              - List subscriptions")
        print("  python subscriptions.py detect       - Detect from transactions")
        print("  python subscriptions.py detect --add - Auto-add detected")
        print("  python subscriptions.py add <name> <amount> [cycle]")
        print("  python subscriptions.py remove <id>")
