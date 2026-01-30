#!/usr/bin/env python3
"""
Currency conversion module for Personal Finance Skill
Uses Frankfurter API (free, no API key required) for exchange rates
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Tuple

import requests

try:
    from config import EXCHANGE_RATE_CACHE_HOURS, DEFAULT_HOME_CURRENCY
except ImportError:
    EXCHANGE_RATE_CACHE_HOURS = 24
    DEFAULT_HOME_CURRENCY = "EUR"

from db import (
    get_cached_rate,
    get_latest_cached_rate,
    cache_exchange_rate,
    cache_exchange_rates_bulk,
    get_home_currency,
    set_home_currency,
)

logger = logging.getLogger(__name__)

# Frankfurter API (free, uses ECB data)
FRANKFURTER_BASE_URL = "https://api.frankfurter.app"

# Common currency symbols for display
CURRENCY_SYMBOLS = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "CHF": "Fr.",
    "JPY": "¥",
    "CNY": "¥",
    "AUD": "A$",
    "CAD": "C$",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "PLN": "zł",
    "CZK": "Kč",
    "HUF": "Ft",
    "RON": "lei",
    "BGN": "лв",
    "HRK": "kn",
    "TRY": "₺",
    "INR": "₹",
    "BRL": "R$",
    "MXN": "$",
    "ZAR": "R",
    "SGD": "S$",
    "HKD": "HK$",
    "NZD": "NZ$",
    "KRW": "₩",
    "THB": "฿",
}


def get_currency_symbol(currency: str) -> str:
    """Get symbol for currency code, fallback to code itself"""
    return CURRENCY_SYMBOLS.get(currency.upper(), currency.upper())


def fetch_exchange_rate(base: str, target: str, rate_date: str = None) -> Optional[float]:
    """
    Fetch exchange rate from Frankfurter API

    Args:
        base: Base currency code (e.g., "EUR")
        target: Target currency code (e.g., "USD")
        rate_date: Date for historical rate (YYYY-MM-DD), None for latest

    Returns:
        Exchange rate as float, or None if fetch failed
    """
    base = base.upper()
    target = target.upper()

    if base == target:
        return 1.0

    try:
        if rate_date:
            url = f"{FRANKFURTER_BASE_URL}/{rate_date}"
        else:
            url = f"{FRANKFURTER_BASE_URL}/latest"

        response = requests.get(
            url,
            params={"from": base, "to": target},
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        rate = data.get("rates", {}).get(target)

        if rate:
            # Cache the rate
            actual_date = data.get("date", date.today().isoformat())
            cache_exchange_rate(base, target, rate, actual_date)

        return rate

    except requests.RequestException as e:
        logger.warning(f"Failed to fetch exchange rate {base}/{target}: {e}")
        return None


def fetch_all_rates(base: str = "EUR", rate_date: str = None) -> Dict[str, float]:
    """
    Fetch all available exchange rates for a base currency

    Args:
        base: Base currency code
        rate_date: Date for historical rates (YYYY-MM-DD), None for latest

    Returns:
        Dictionary of {currency_code: rate}
    """
    base = base.upper()

    try:
        if rate_date:
            url = f"{FRANKFURTER_BASE_URL}/{rate_date}"
        else:
            url = f"{FRANKFURTER_BASE_URL}/latest"

        response = requests.get(
            url,
            params={"from": base},
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        rates = data.get("rates", {})
        actual_date = data.get("date", date.today().isoformat())

        if rates:
            # Cache all rates
            cache_exchange_rates_bulk(base, rates, actual_date)

        return rates

    except requests.RequestException as e:
        logger.warning(f"Failed to fetch exchange rates for {base}: {e}")
        return {}


def get_exchange_rate(base: str, target: str, rate_date: str = None) -> Optional[float]:
    """
    Get exchange rate, using cache when available

    Args:
        base: Base currency code
        target: Target currency code
        rate_date: Date for historical rate (YYYY-MM-DD), None for today

    Returns:
        Exchange rate as float, or None if unavailable
    """
    base = base.upper()
    target = target.upper()

    if base == target:
        return 1.0

    if rate_date is None:
        rate_date = date.today().isoformat()

    # Try cache first
    cached = get_cached_rate(base, target, rate_date)
    if cached is not None:
        return cached

    # Check if we have a recent cached rate (within cache hours)
    latest = get_latest_cached_rate(base, target)
    if latest:
        rate, cached_date = latest
        cached_datetime = datetime.fromisoformat(cached_date)
        if datetime.now() - cached_datetime < timedelta(hours=EXCHANGE_RATE_CACHE_HOURS):
            return rate

    # Fetch fresh rate
    return fetch_exchange_rate(base, target, rate_date)


def convert(amount: float, from_currency: str, to_currency: str,
            rate_date: str = None) -> Optional[Tuple[float, float]]:
    """
    Convert amount between currencies

    Args:
        amount: Amount to convert
        from_currency: Source currency code
        to_currency: Target currency code
        rate_date: Date for historical rate (YYYY-MM-DD)

    Returns:
        Tuple of (converted_amount, rate_used), or None if conversion failed
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return (amount, 1.0)

    rate = get_exchange_rate(from_currency, to_currency, rate_date)
    if rate is None:
        return None

    return (amount * rate, rate)


def convert_to_home(amount: float, from_currency: str,
                    rate_date: str = None) -> Optional[Tuple[float, str, float]]:
    """
    Convert amount to user's home currency

    Args:
        amount: Amount to convert
        from_currency: Source currency code
        rate_date: Date for historical rate

    Returns:
        Tuple of (converted_amount, home_currency, rate_used), or None if failed
    """
    home = get_home_currency()
    result = convert(amount, from_currency, home, rate_date)

    if result is None:
        return None

    return (result[0], home, result[1])


def format_amount(amount: float, currency: str, show_symbol: bool = True) -> str:
    """
    Format amount with currency symbol

    Args:
        amount: Amount to format
        currency: Currency code
        show_symbol: Whether to show symbol or code

    Returns:
        Formatted string like "€1,234.56" or "1,234.56 EUR"
    """
    currency = currency.upper()

    if show_symbol:
        symbol = get_currency_symbol(currency)
        # Some currencies put symbol after (e.g., 1.234,56 €)
        if currency in ["EUR", "CHF", "PLN", "CZK", "HUF", "SEK", "NOK", "DKK"]:
            return f"{amount:,.2f} {symbol}"
        else:
            return f"{symbol}{amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def format_with_conversion(amount: float, original_currency: str,
                           rate_date: str = None) -> str:
    """
    Format amount with optional conversion to home currency

    Args:
        amount: Amount in original currency
        original_currency: Original currency code
        rate_date: Date for historical rate

    Returns:
        Formatted string, e.g., "45.50 CHF (€42.32)" or just "€45.50"
    """
    original_currency = original_currency.upper()
    home = get_home_currency()

    original_str = format_amount(amount, original_currency)

    if original_currency == home:
        return original_str

    result = convert(amount, original_currency, home, rate_date)
    if result:
        converted, rate = result
        home_str = format_amount(converted, home)
        return f"{original_str} ({home_str})"

    return original_str


def get_supported_currencies() -> list:
    """Get list of currencies supported by Frankfurter API"""
    try:
        response = requests.get(f"{FRANKFURTER_BASE_URL}/currencies", timeout=10)
        response.raise_for_status()
        return list(response.json().keys())
    except requests.RequestException:
        # Return common currencies as fallback
        return list(CURRENCY_SYMBOLS.keys())


# Convenience functions for common operations

def to_home(amount: float, currency: str) -> float:
    """Quick conversion to home currency, returns original if conversion fails"""
    result = convert_to_home(amount, currency)
    return result[0] if result else amount


def home_symbol() -> str:
    """Get symbol for user's home currency"""
    return get_currency_symbol(get_home_currency())


if __name__ == "__main__":
    # Test the module
    print("Currency Module Test")
    print("=" * 40)

    # Test fetching rates
    print("\nFetching EUR/USD rate...")
    rate = get_exchange_rate("EUR", "USD")
    print(f"  EUR/USD: {rate}")

    # Test conversion
    print("\nConverting 100 CHF to EUR...")
    result = convert(100, "CHF", "EUR")
    if result:
        print(f"  100 CHF = {result[0]:.2f} EUR (rate: {result[1]:.4f})")

    # Test formatting
    print("\nFormatting examples:")
    print(f"  {format_amount(1234.56, 'EUR')}")
    print(f"  {format_amount(1234.56, 'USD')}")
    print(f"  {format_amount(1234.56, 'CHF')}")

    # Test with conversion
    print("\nFormat with conversion (home=EUR):")
    set_home_currency("EUR")
    print(f"  {format_with_conversion(100, 'CHF')}")
    print(f"  {format_with_conversion(100, 'USD')}")
    print(f"  {format_with_conversion(100, 'EUR')}")

    print("\n✅ Currency module working!")
