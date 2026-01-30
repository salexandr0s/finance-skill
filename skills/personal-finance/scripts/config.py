#!/usr/bin/env python3
"""
Configuration settings for Personal Finance Skill
Centralized location for all configurable values
"""

# Currency settings
DEFAULT_HOME_CURRENCY = "EUR"  # Default currency for display (user can override)
EXCHANGE_RATE_CACHE_HOURS = 24  # How long to cache exchange rates
EXCHANGE_RATE_API = "frankfurter"  # API source: "frankfurter" (free, no key needed)

# Rate limiting
DAILY_API_CALL_LIMIT = 3  # Max API calls per day per account

# Chart generation
PIE_CHART_MINIMUM_PERCENTAGE = 0.03  # 3% minimum to show in pie chart (smaller grouped as "Other")
CHART_RETENTION_DAYS = 7  # Days to keep old chart files before cleanup

# Categorization thresholds
SMALL_AMOUNT_THRESHOLD = 5  # CHF - amounts below this may be fees/subscriptions
LARGE_AMOUNT_THRESHOLD = 1000  # CHF - amounts above this may be housing/salary

# API settings
API_TIMEOUT_SECONDS = 60  # Timeout for GoCardless API calls

# Database settings
DB_FILE_PERMISSIONS = 0o600  # Owner read/write only
CREDENTIAL_FILE_PERMISSIONS = 0o600  # Owner read/write only
