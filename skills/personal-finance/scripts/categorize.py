#!/usr/bin/env python3
"""
Transaction categorization engine
Auto-categorizes transactions using rule-based matching
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from db import get_recent_transactions, update_transaction_categories

# Load categories from config
def load_categories() -> Dict:
    """Load category definitions and rules"""
    categories_file = Path(__file__).parent.parent / 'config' / 'categories.json'
    
    try:
        with open(categories_file) as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default categories if file doesn't exist
        return get_default_categories()

def get_default_categories() -> Dict:
    """Default category definitions"""
    return {
        "categories": [
            {
                "name": "groceries",
                "emoji": "🛒",
                "keywords": [
                    "migros", "coop", "manor", "denner", "aldi", "lidl", "spar",
                    "volg", "aperto", "supermarket", "grocery", "lebensmittel",
                    "epicerie", "grocery"
                ],
                "patterns": [
                    r"(?i)migros.*",
                    r"(?i)coop.*",
                    r"(?i).*supermarkt.*",
                    r"(?i).*grocery.*"
                ]
            },
            {
                "name": "dining",
                "emoji": "🍽️",
                "keywords": [
                    "restaurant", "cafe", "starbucks", "mcdonald", "burger king",
                    "subway", "pizza", "kebab", "bistro", "bar", "pub",
                    "takeaway", "delivery", "uber eats", "just eat"
                ],
                "patterns": [
                    r"(?i).*restaurant.*",
                    r"(?i).*cafe.*",
                    r"(?i).*pizza.*",
                    r"(?i)starbucks.*",
                    r"(?i)mc.*donald.*"
                ]
            },
            {
                "name": "transport",
                "emoji": "🚃",
                "keywords": [
                    "sbb", "zvv", "tpg", "vbl", "uber", "taxi", "parking",
                    "tankstelle", "petrol", "gas", "mobility", "car2go",
                    "share now", "publibike", "lime", "bird", "tier"
                ],
                "patterns": [
                    r"(?i)sbb.*",
                    r"(?i)zvv.*",
                    r"(?i).*taxi.*",
                    r"(?i).*parking.*",
                    r"(?i).*tankstelle.*",
                    r"(?i)uber.*"
                ]
            },
            {
                "name": "shopping",
                "emoji": "🛍️", 
                "keywords": [
                    "amazon", "zalando", "h&m", "zara", "manor", "globus",
                    "interdiscount", "digitec", "galaxus", "media markt",
                    "ikea", "bauhaus", "obi", "landi", "jumbo"
                ],
                "patterns": [
                    r"(?i)amazon.*",
                    r"(?i)zalando.*",
                    r"(?i)digitec.*",
                    r"(?i)galaxus.*"
                ]
            },
            {
                "name": "subscriptions",
                "emoji": "📺",
                "keywords": [
                    "netflix", "spotify", "apple", "google", "microsoft",
                    "adobe", "dropbox", "icloud", "youtube", "prime",
                    "disney", "swisscom", "sunrise", "salt", "upc"
                ],
                "patterns": [
                    r"(?i)netflix.*",
                    r"(?i)spotify.*",
                    r"(?i)apple.*subscription.*",
                    r"(?i).*monthly.*",
                    r"(?i).*subscription.*"
                ]
            },
            {
                "name": "utilities",
                "emoji": "⚡",
                "keywords": [
                    "ewz", "swisscom", "sunrise", "salt", "swissgas",
                    "energie", "electricity", "water", "heating", "internet",
                    "phone", "mobile", "insurance", "versicherung"
                ],
                "patterns": [
                    r"(?i).*energie.*",
                    r"(?i).*electricity.*",
                    r"(?i).*versicherung.*",
                    r"(?i).*insurance.*"
                ]
            },
            {
                "name": "entertainment",
                "emoji": "🎮",
                "keywords": [
                    "cinema", "kino", "theater", "concert", "tickets",
                    "steam", "playstation", "xbox", "nintendo", "game",
                    "ticketcorner", "starticket", "eventim"
                ],
                "patterns": [
                    r"(?i).*cinema.*",
                    r"(?i).*kino.*",
                    r"(?i).*tickets.*",
                    r"(?i)steam.*"
                ]
            },
            {
                "name": "health",
                "emoji": "🏥",
                "keywords": [
                    "pharmacy", "apotheke", "doctor", "dentist", "hospital",
                    "zahnarzt", "arzt", "medizin", "fitness", "gym",
                    "physiotherapy", "massage"
                ],
                "patterns": [
                    r"(?i).*apotheke.*",
                    r"(?i).*pharmacy.*",
                    r"(?i).*medical.*",
                    r"(?i).*fitness.*"
                ]
            },
            {
                "name": "housing",
                "emoji": "🏠",
                "keywords": [
                    "rent", "miete", "mortgage", "hypothek", "utilities",
                    "cleaning", "maintenance", "repairs", "furniture"
                ],
                "patterns": [
                    r"(?i).*miete.*",
                    r"(?i).*rent.*",
                    r"(?i).*hypothek.*"
                ]
            },
            {
                "name": "transfers",
                "emoji": "↔️",
                "keywords": [
                    "twint", "transfer", "überweisung", "paypal", "revolut",
                    "wise", "westernunion", "bank transfer"
                ],
                "patterns": [
                    r"(?i)twint.*",
                    r"(?i).*transfer.*",
                    r"(?i).*überweisung.*"
                ]
            }
        ],
        "mcc_mappings": {
            "5411": "groceries",    # Grocery Stores
            "5812": "dining",       # Eating Places
            "5814": "dining",       # Fast Food Restaurants  
            "4111": "transport",    # Transportation - Suburban and Local
            "4121": "transport",    # Taxicabs/Limousines
            "5541": "transport",    # Service Stations
            "5300": "shopping",     # Wholesale Clubs
            "5651": "shopping",     # Family Clothing Stores
            "5732": "shopping",     # Electronics Stores
            "4899": "utilities",    # Cable, Satellite, and Other Pay TV
            "5968": "entertainment" # Direct Marketing - Continuity/Subscription
        }
    }

def categorize_transaction(transaction: Dict) -> str:
    """Categorize a single transaction"""
    # Try different categorization methods in order of priority
    
    # 1. User overrides (already handled in database)
    if transaction.get('category_source') == 'user':
        return transaction.get('category', 'other')
    
    # 2. Merchant/creditor name matching
    creditor = transaction.get('creditor_name', '') or ''
    debtor = transaction.get('debtor_name', '') or ''
    description = transaction.get('description', '') or ''
    
    # Combine all text for matching
    combined_text = f"{creditor} {debtor} {description}".lower()
    
    # Load categories
    categories_config = load_categories()
    
    # 3. Pattern matching (most specific first)
    for category_def in categories_config['categories']:
        category_name = category_def['name']
        
        # Check regex patterns
        for pattern in category_def.get('patterns', []):
            if re.search(pattern, combined_text):
                return category_name
                
        # Check keywords
        for keyword in category_def.get('keywords', []):
            if keyword.lower() in combined_text:
                return category_name
    
    # 4. MCC code mapping (if available)
    mcc_code = transaction.get('mcc_code')
    if mcc_code:
        mcc_mappings = categories_config.get('mcc_mappings', {})
        if mcc_code in mcc_mappings:
            return mcc_mappings[mcc_code]
    
    # 5. Amount-based heuristics
    amount = float(transaction.get('amount', 0))
    
    # Positive amounts (income)
    if amount > 0:
        if amount > 1000:  # Large deposits likely salary/income
            return 'income'
        else:
            return 'transfers'  # Small deposits likely transfers
    
    # Negative amounts (expenses)
    amount = abs(amount)
    
    # Very small amounts often fees or digital purchases
    if amount < 5:
        if any(word in combined_text for word in ['fee', 'gebühr', 'charge']):
            return 'utilities'
        else:
            return 'subscriptions'
    
    # Large amounts often rent/mortgage
    if amount > 1000:
        return 'housing'
    
    # 6. Time-based heuristics
    booking_date = transaction.get('booking_date', '')
    if booking_date:
        # Weekend transactions more likely to be dining/entertainment
        try:
            from datetime import datetime
            date_obj = datetime.fromisoformat(booking_date)
            if date_obj.weekday() >= 5:  # Saturday/Sunday
                if 20 <= amount <= 150:  # Typical restaurant range
                    return 'dining'
        except (ValueError, TypeError):
            # ValueError for invalid date format, TypeError for None values
            pass
    
    # 7. Default fallback
    return 'other'

def auto_categorize_recent(days: int = 7) -> int:
    """Auto-categorize recent uncategorized transactions"""
    transactions = get_recent_transactions(days)
    
    if not transactions:
        return 0
    
    category_updates = {}
    
    for transaction in transactions:
        category = categorize_transaction(transaction)
        if category and category != 'other':
            category_updates[transaction['id']] = category
    
    if category_updates:
        update_transaction_categories(category_updates)
        
    return len(category_updates)

def categorize_batch(transactions: List[Dict]) -> Dict[str, str]:
    """Categorize multiple transactions"""
    results = {}
    
    for transaction in transactions:
        category = categorize_transaction(transaction)
        results[transaction['id']] = category
        
    return results

def add_merchant_rule(merchant_pattern: str, category: str) -> bool:
    """Add new merchant categorization rule"""
    try:
        categories_file = Path(__file__).parent.parent / 'config' / 'categories.json'
        
        # Load existing config
        if categories_file.exists():
            with open(categories_file) as f:
                config = json.load(f)
        else:
            config = get_default_categories()
            categories_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Find category and add pattern
        for category_def in config['categories']:
            if category_def['name'] == category.lower():
                if 'patterns' not in category_def:
                    category_def['patterns'] = []
                
                # Add case-insensitive pattern
                pattern = f"(?i).*{re.escape(merchant_pattern)}.*"
                if pattern not in category_def['patterns']:
                    category_def['patterns'].append(pattern)
                    
                # Save updated config
                with open(categories_file, 'w') as f:
                    json.dump(config, f, indent=2)
                    
                return True
                
        return False  # Category not found
        
    except Exception as e:
        print(f"Error adding merchant rule: {e}")
        return False

def get_category_stats() -> Dict[str, Dict]:
    """Get categorization statistics"""
    from db import get_db
    
    with get_db() as conn:
        # Get total transactions by category
        cursor = conn.execute("""
            SELECT 
                COALESCE(category, 'uncategorized') as category,
                COUNT(*) as count,
                SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as expense_total,
                AVG(CASE WHEN amount < 0 THEN ABS(amount) ELSE NULL END) as avg_expense
            FROM transactions
            WHERE booking_date >= date('now', '-3 months')
            GROUP BY COALESCE(category, 'uncategorized')
            ORDER BY count DESC
        """)
        
        stats = {}
        for row in cursor.fetchall():
            stats[row['category']] = {
                'transaction_count': row['count'],
                'total_spent': row['expense_total'] or 0,
                'average_amount': row['avg_expense'] or 0
            }
            
        return stats

def suggest_recategorization() -> List[Dict]:
    """Suggest transactions that might be miscategorized"""
    from db import get_db
    
    suggestions = []
    
    with get_db() as conn:
        # Find transactions with unusual amounts for their category
        cursor = conn.execute("""
            WITH category_stats AS (
                SELECT 
                    category,
                    AVG(ABS(amount)) as avg_amount,
                    AVG(ABS(amount)) * 2 as threshold_high,
                    AVG(ABS(amount)) / 2 as threshold_low
                FROM transactions 
                WHERE category IS NOT NULL 
                AND amount < 0
                AND booking_date >= date('now', '-6 months')
                GROUP BY category
                HAVING COUNT(*) >= 5
            )
            SELECT 
                t.id, 
                t.creditor_name, 
                t.description,
                t.amount,
                t.category,
                s.avg_amount,
                CASE 
                    WHEN ABS(t.amount) > s.threshold_high THEN 'unusually_high'
                    WHEN ABS(t.amount) < s.threshold_low THEN 'unusually_low'
                END as anomaly_type
            FROM transactions t
            JOIN category_stats s ON t.category = s.category
            WHERE t.booking_date >= date('now', '-1 month')
            AND (ABS(t.amount) > s.threshold_high OR ABS(t.amount) < s.threshold_low)
            ORDER BY t.booking_date DESC
            LIMIT 20
        """)
        
        for row in cursor.fetchall():
            suggestions.append({
                'transaction_id': row['id'],
                'merchant': row['creditor_name'],
                'description': row['description'],
                'amount': row['amount'],
                'current_category': row['category'],
                'anomaly': row['anomaly_type'],
                'category_average': row['avg_amount']
            })
    
    return suggestions

def export_categorization_rules() -> str:
    """Export current categorization rules to JSON string"""
    config = load_categories()
    return json.dumps(config, indent=2)

def import_categorization_rules(json_data: str) -> bool:
    """Import categorization rules from JSON string"""
    try:
        config = json.loads(json_data)
        
        # Validate structure
        if 'categories' not in config:
            return False
            
        categories_file = Path(__file__).parent.parent / 'config' / 'categories.json'
        categories_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(categories_file, 'w') as f:
            json.dump(config, f, indent=2)
            
        return True
        
    except Exception as e:
        print(f"Error importing rules: {e}")
        return False

if __name__ == '__main__':
    # Test categorization
    test_transactions = [
        {
            'id': 'test1',
            'creditor_name': 'MIGROS ZURICH',
            'description': 'Kartenzahlung',
            'amount': -45.50
        },
        {
            'id': 'test2', 
            'creditor_name': 'STARBUCKS',
            'description': 'Coffee',
            'amount': -6.80
        },
        {
            'id': 'test3',
            'creditor_name': 'SBB',
            'description': 'Train ticket',
            'amount': -23.40
        }
    ]
    
    print("Testing categorization...")
    for txn in test_transactions:
        category = categorize_transaction(txn)
        print(f"{txn['creditor_name']} → {category}")
    
    print(f"\nCategory statistics:")
    stats = get_category_stats()
    for category, data in stats.items():
        print(f"{category}: {data['transaction_count']} transactions, {data['total_spent']:.2f} CHF total")