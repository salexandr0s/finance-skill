#!/usr/bin/env python3
"""
Optional Notion export for Personal Finance skill.
Exports transactions from local SQLite to a Notion database.

Usage:
    python3 notion_export.py --month 1 --year 2026
    python3 notion_export.py --all
    
Environment:
    NOTION_API_KEY - Your Notion integration token
    NOTION_TRANSACTIONS_DB - Database ID for transactions
"""

import argparse
import os
import sys
from datetime import datetime
from calendar import monthrange
from pathlib import Path

import requests

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from db import get_db_path, get_transactions
try:
    import keychain
    HAS_KEYCHAIN = True
except ImportError:
    HAS_KEYCHAIN = False


def get_notion_api_key():
    """Get Notion API key from keychain or environment."""
    if HAS_KEYCHAIN:
        key = keychain.get("notion_api_key")
        if key:
            return key
    key = os.environ.get("NOTION_API_KEY")
    if not key:
        raise ValueError("Notion API key not found. Set NOTION_API_KEY env var or use keychain.")
    return key


def get_transactions_db():
    """Get Notion transactions database ID."""
    if HAS_KEYCHAIN:
        db_id = keychain.get("notion_transactions_db")
        if db_id:
            return db_id
    db_id = os.environ.get("NOTION_TRANSACTIONS_DB")
    if not db_id:
        raise ValueError("Notion database ID not found. Set NOTION_TRANSACTIONS_DB env var.")
    return db_id


def create_notion_page(tx: dict, api_key: str, db_id: str) -> dict:
    """Create a transaction page in Notion."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    properties = {
        "Description": {"title": [{"text": {"content": tx.get("description", "")[:100]}}]},
        "Date": {"date": {"start": tx.get("date", "")}},
        "Amount": {"number": tx.get("amount", 0)},
        "Currency": {"select": {"name": tx.get("currency", "EUR")}},
        "Type": {"select": {"name": "Expense" if tx.get("amount", 0) < 0 else "Income"}},
        "Category": {"select": {"name": tx.get("category", "Other")}},
        "Account": {"select": {"name": tx.get("account", "Default")}},
    }
    
    data = {
        "parent": {"database_id": db_id},
        "properties": properties
    }
    
    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers=headers,
        json=data
    )
    
    return response.json()


def check_existing(date: str, amount: float, api_key: str, db_id: str) -> bool:
    """Check if transaction already exists in Notion."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    query = {
        "filter": {
            "and": [
                {"property": "Date", "date": {"equals": date}},
                {"property": "Amount", "number": {"equals": amount}}
            ]
        },
        "page_size": 5
    }
    
    response = requests.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers=headers,
        json=query
    )
    
    results = response.json().get("results", [])
    return len(results) > 0


def export_to_notion(transactions: list, skip_duplicates: bool = True):
    """Export transactions to Notion."""
    api_key = get_notion_api_key()
    db_id = get_transactions_db()
    
    exported = 0
    skipped = 0
    errors = 0
    
    for tx in transactions:
        if skip_duplicates:
            if check_existing(tx.get("date", ""), tx.get("amount", 0), api_key, db_id):
                skipped += 1
                continue
        
        try:
            result = create_notion_page(tx, api_key, db_id)
            if "id" in result:
                exported += 1
            else:
                errors += 1
                print(f"Error: {result.get('message', 'Unknown')}")
        except Exception as e:
            errors += 1
            print(f"Error: {e}")
    
    return {"exported": exported, "skipped": skipped, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description="Export transactions to Notion")
    parser.add_argument("--month", "-m", type=int, help="Month (1-12)")
    parser.add_argument("--year", "-y", type=int, help="Year")
    parser.add_argument("--all", action="store_true", help="Export all transactions")
    parser.add_argument("--no-skip-duplicates", action="store_true", help="Don't skip duplicates")
    args = parser.parse_args()
    
    # Get transactions from local DB
    if args.all:
        transactions = get_transactions()
    elif args.month and args.year:
        start_date = f"{args.year}-{args.month:02d}-01"
        _, last_day = monthrange(args.year, args.month)
        end_date = f"{args.year}-{args.month:02d}-{last_day}"
        transactions = get_transactions(start_date=start_date, end_date=end_date)
    else:
        # Default to current month
        now = datetime.now()
        start_date = f"{now.year}-{now.month:02d}-01"
        _, last_day = monthrange(now.year, now.month)
        end_date = f"{now.year}-{now.month:02d}-{last_day}"
        transactions = get_transactions(start_date=start_date, end_date=end_date)
    
    print(f"Found {len(transactions)} transactions to export")
    
    result = export_to_notion(transactions, skip_duplicates=not args.no_skip_duplicates)
    
    print(f"\n✓ Export complete:")
    print(f"  Exported: {result['exported']}")
    print(f"  Skipped (duplicates): {result['skipped']}")
    print(f"  Errors: {result['errors']}")


if __name__ == "__main__":
    main()
