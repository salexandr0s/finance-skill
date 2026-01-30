#!/usr/bin/env python3
"""
Crypto wallet integration via Zerion API
Supports EVM chains (Ethereum, Polygon, etc.) and Solana
"""

import requests
import base64
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

# Import configuration
try:
    from config import (
        ZERION_API_BASE, ZERION_API_TIMEOUT, WALLET_SYNC_CACHE_HOURS,
        SUPPORTED_CHAINS, CREDENTIAL_FILE_PERMISSIONS
    )
except ImportError:
    ZERION_API_BASE = "https://api.zerion.io/v1"
    ZERION_API_TIMEOUT = 30
    WALLET_SYNC_CACHE_HOURS = 1
    CREDENTIAL_FILE_PERMISSIONS = 0o600
    SUPPORTED_CHAINS = {
        'ethereum': 'ethereum', 'eth': 'ethereum',
        'polygon': 'polygon', 'matic': 'polygon',
        'arbitrum': 'arbitrum', 'optimism': 'optimism',
        'base': 'base', 'solana': 'solana', 'sol': 'solana',
        'avalanche': 'avalanche', 'bsc': 'binance-smart-chain',
        'fantom': 'fantom', 'zksync': 'zksync-era',
    }

# Keychain support (same pattern as gocardless.py)
try:
    import keyring
    KEYCHAIN_AVAILABLE = True
except ImportError:
    KEYCHAIN_AVAILABLE = False
    logger.warning("Keychain not available, falling back to file storage for Zerion credentials")

KEYCHAIN_SERVICE = 'clawdbot-finance'
ZERION_CREDS_FILE = Path.home() / '.config' / 'zerion_creds.json'


# ============================================================================
# Credential Management
# ============================================================================

def get_zerion_api_key() -> Optional[str]:
    """Get Zerion API key from keychain or file"""
    if KEYCHAIN_AVAILABLE:
        try:
            key = keyring.get_password(KEYCHAIN_SERVICE, 'zerion_api_key')
            if key:
                return key
        except Exception as e:
            logger.debug(f"Keychain read failed: {e}")

    # File fallback
    if ZERION_CREDS_FILE.exists():
        try:
            with open(ZERION_CREDS_FILE, 'r') as f:
                creds = json.load(f)
                return creds.get('api_key')
        except Exception as e:
            logger.debug(f"Creds file read failed: {e}")

    return None


def save_zerion_api_key(api_key: str) -> bool:
    """Save Zerion API key to keychain or file"""
    try:
        if KEYCHAIN_AVAILABLE:
            try:
                keyring.set_password(KEYCHAIN_SERVICE, 'zerion_api_key', api_key)
                logger.info("Zerion API key saved to keychain")
                return True
            except Exception as e:
                logger.warning(f"Keychain save failed, using file: {e}")

        # File fallback
        ZERION_CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ZERION_CREDS_FILE, 'w') as f:
            json.dump({'api_key': api_key}, f)
        os.chmod(ZERION_CREDS_FILE, CREDENTIAL_FILE_PERMISSIONS)
        logger.info(f"Zerion API key saved to {ZERION_CREDS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save Zerion API key: {e}")
        return False


def has_zerion_credentials() -> bool:
    """Check if Zerion API key is configured"""
    return get_zerion_api_key() is not None


# ============================================================================
# Zerion API Client
# ============================================================================

class ZerionClient:
    """Client for Zerion API"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or get_zerion_api_key()
        if not self.api_key:
            raise ValueError("Zerion API key not configured. Run /finance setup or /finance wallet add")

        self.base_url = ZERION_API_BASE
        self.session = requests.Session()

        # Basic auth with API key (Zerion uses API key as username, empty password)
        encoded = base64.b64encode(f"{self.api_key}:".encode()).decode()
        self.session.headers['Authorization'] = f'Basic {encoded}'
        self.session.headers['Accept'] = 'application/json'

    def get_portfolio(self, address: str, currency: str = 'usd') -> Dict:
        """
        Get total portfolio value for a wallet

        Returns portfolio breakdown by position type and chain
        """
        url = f"{self.base_url}/wallets/{address}/portfolio"
        params = {'currency': currency}

        try:
            response = self.session.get(url, params=params, timeout=ZERION_API_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Zerion portfolio request failed for {address[:8]}...: {e}")
            raise

    def get_positions(self, address: str,
                      chains: List[str] = None,
                      currency: str = 'usd',
                      limit: int = 50) -> List[Dict]:
        """
        Get all token positions for a wallet

        Returns list of position objects with token info, balances, and values
        """
        url = f"{self.base_url}/wallets/{address}/positions/"
        params = {
            'currency': currency,
            'filter[trash]': 'only_non_trash',
            'filter[positions]': 'only_simple',  # Just wallet holdings, not DeFi
            'sort': '-value',
            'page[size]': limit
        }

        if chains:
            # Map user-friendly names to Zerion chain IDs
            chain_ids = [SUPPORTED_CHAINS.get(c.lower(), c) for c in chains]
            params['filter[chain_ids]'] = ','.join(chain_ids)

        try:
            response = self.session.get(url, params=params, timeout=ZERION_API_TIMEOUT)
            response.raise_for_status()
            return response.json().get('data', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Zerion positions request failed for {address[:8]}...: {e}")
            raise

    def validate_address(self, address: str) -> bool:
        """Check if an address is valid by attempting to fetch portfolio"""
        try:
            self.get_portfolio(address)
            return True
        except Exception:
            return False


# ============================================================================
# Wallet Operations
# ============================================================================

def get_wallet_value(address: str, blockchain: str = None) -> Tuple[float, List[Dict]]:
    """
    Get wallet total value and top positions

    Args:
        address: Wallet address
        blockchain: Optional chain filter (e.g., 'ethereum', 'solana')

    Returns:
        Tuple of (total_usd, positions_list)
    """
    try:
        client = ZerionClient()

        # Get portfolio total
        portfolio = client.get_portfolio(address)
        total_usd = 0.0

        # Extract total value from portfolio
        if 'data' in portfolio and 'attributes' in portfolio['data']:
            attrs = portfolio['data']['attributes']
            # Sum positions by type (wallet, deposited, etc.)
            positions_distribution = attrs.get('positions_distribution_by_type', {})
            for pos_type, value in positions_distribution.items():
                if isinstance(value, (int, float)):
                    total_usd += value

        # Get detailed positions
        chains = [blockchain] if blockchain else None
        positions_data = client.get_positions(address, chains=chains)

        # Parse positions into simpler format
        positions = []
        for pos in positions_data:
            if 'attributes' not in pos:
                continue

            attrs = pos['attributes']
            fungible = attrs.get('fungible_info', {})

            position = {
                'symbol': fungible.get('symbol', 'UNKNOWN'),
                'name': fungible.get('name', 'Unknown Token'),
                'quantity': attrs.get('quantity', {}).get('float', 0),
                'value_usd': attrs.get('value', 0),
                'price_usd': attrs.get('price', 0),
                'chain': attrs.get('chain_id', 'unknown'),
                'position_type': attrs.get('position_type', 'wallet'),
            }
            positions.append(position)

        # If we didn't get total from portfolio, sum positions
        if total_usd == 0 and positions:
            total_usd = sum(p['value_usd'] for p in positions if p['value_usd'])

        return total_usd, positions

    except Exception as e:
        logger.error(f"Failed to get wallet value for {address[:8]}...: {e}")
        return 0.0, []


def sync_wallet(wallet_id: str, address: str, blockchain: str = None) -> Tuple[float, bool]:
    """
    Sync a single wallet and save snapshot

    Returns:
        Tuple of (total_usd, success)
    """
    from db import save_wallet_snapshot

    try:
        total_usd, positions = get_wallet_value(address, blockchain)

        # Save snapshot with positions JSON
        positions_json = json.dumps(positions) if positions else None
        success = save_wallet_snapshot(wallet_id, total_usd, positions_json)

        return total_usd, success
    except Exception as e:
        logger.error(f"Failed to sync wallet {address[:8]}...: {e}")
        return 0.0, False


def sync_all_wallets(force: bool = False) -> Dict[str, float]:
    """
    Sync all stored wallets and return totals

    Args:
        force: If True, sync even if recently synced

    Returns:
        Dict mapping wallet_id to total_usd
    """
    from db import get_wallets, get_latest_wallet_snapshot

    wallets = get_wallets()
    if not wallets:
        return {}

    results = {}
    cache_cutoff = datetime.now() - timedelta(hours=WALLET_SYNC_CACHE_HOURS)

    for wallet in wallets:
        wallet_id = wallet['id']
        address = wallet['address']
        blockchain = wallet['blockchain']

        # Check if we need to sync (unless forced)
        if not force:
            snapshot = get_latest_wallet_snapshot(wallet_id)
            if snapshot:
                snapshot_time = datetime.fromisoformat(snapshot['created_at'].replace('Z', '+00:00'))
                if snapshot_time > cache_cutoff:
                    # Use cached value
                    results[wallet_id] = snapshot['total_value_usd']
                    continue

        # Sync wallet
        total_usd, success = sync_wallet(wallet_id, address, blockchain)
        results[wallet_id] = total_usd

    return results


def format_wallet_summary(include_positions: bool = False, home_currency: str = None) -> str:
    """
    Format wallet balances for display

    Args:
        include_positions: If True, include token breakdown
        home_currency: Convert to this currency (default: user's home currency)

    Returns:
        Formatted string for display
    """
    from db import get_wallets, get_latest_wallet_snapshot

    # Get home currency for conversion
    if home_currency is None:
        try:
            from db import get_home_currency
            home_currency = get_home_currency()
        except ImportError:
            home_currency = 'USD'

    wallets = get_wallets()
    if not wallets:
        return "No crypto wallets configured. Use `/finance wallet add` to add one."

    lines = ["🪙 **Crypto Wallets:**", ""]
    total_usd = 0.0

    for wallet in wallets:
        snapshot = get_latest_wallet_snapshot(wallet['id'])
        label = wallet['label'] or f"{wallet['blockchain'].title()} Wallet"
        address_short = f"{wallet['address'][:6]}...{wallet['address'][-4:]}"

        if snapshot:
            value_usd = snapshot['total_value_usd']
            total_usd += value_usd

            # Format value in home currency
            value_str = format_crypto_value(value_usd, home_currency)
            lines.append(f"**{label}** ({address_short})")
            lines.append(f"  Total: {value_str}")

            # Add position breakdown if requested
            if include_positions and snapshot.get('positions_json'):
                positions = json.loads(snapshot['positions_json'])
                for pos in positions[:10]:  # Top 10 positions
                    if pos['value_usd'] >= 1:  # Only show positions worth $1+
                        pos_value = format_crypto_value(pos['value_usd'], home_currency)
                        lines.append(f"    • {pos['symbol']}: {pos['quantity']:.4f} ({pos_value})")

            lines.append("")
        else:
            lines.append(f"**{label}** ({address_short})")
            lines.append(f"  Not synced yet. Run `/finance wallet sync`")
            lines.append("")

    # Total
    if total_usd > 0:
        total_str = format_crypto_value(total_usd, home_currency)
        lines.append(f"**Total Crypto: {total_str}**")

    return "\n".join(lines)


def format_crypto_value(usd_value: float, home_currency: str = None) -> str:
    """
    Format crypto value in user's home currency

    Args:
        usd_value: Value in USD
        home_currency: Target currency (default: user's home currency)

    Returns:
        Formatted string like "€4,234.56 ($4,612.00)" or "$4,612.00"
    """
    if home_currency is None:
        try:
            from db import get_home_currency
            home_currency = get_home_currency()
        except ImportError:
            home_currency = 'USD'

    # If home currency is USD, just return USD value
    if home_currency.upper() == 'USD':
        return f"${usd_value:,.2f}"

    # Try to convert to home currency
    try:
        from currency import convert, get_currency_symbol
        result = convert(usd_value, 'USD', home_currency)

        if result:
            home_value, rate = result
            symbol = get_currency_symbol(home_currency)
            return f"{symbol}{home_value:,.2f} (${usd_value:,.2f})"
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Currency conversion failed: {e}")

    # Fallback to USD only
    return f"${usd_value:,.2f}"


def normalize_chain(chain: str) -> str:
    """Normalize chain name to Zerion format"""
    return SUPPORTED_CHAINS.get(chain.lower(), chain.lower())


def get_supported_chains() -> List[str]:
    """Get list of user-friendly supported chain names"""
    # Return unique chain IDs (not aliases)
    seen = set()
    result = []
    for alias, chain_id in SUPPORTED_CHAINS.items():
        if chain_id not in seen:
            seen.add(chain_id)
            result.append(alias)
    return sorted(result)


# ============================================================================
# CLI Entry Point (for testing)
# ============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python crypto.py <command> [args]")
        print("Commands:")
        print("  setup                    - Configure Zerion API key")
        print("  check <address>          - Check wallet value")
        print("  chains                   - List supported chains")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'setup':
        print("🔧 Zerion API Setup")
        print("=" * 50)
        print("1. Go to https://developers.zerion.io")
        print("2. Sign up for a free account")
        print("3. Get your API key from the dashboard")
        print()

        api_key = input("Enter your Zerion API key: ").strip()
        if api_key:
            if save_zerion_api_key(api_key):
                print("✅ API key saved successfully!")

                # Test the key
                try:
                    client = ZerionClient(api_key)
                    print("✅ API key validated!")
                except Exception as e:
                    print(f"⚠️ Could not validate API key: {e}")
            else:
                print("❌ Failed to save API key")
        else:
            print("❌ No API key provided")

    elif command == 'check':
        if len(sys.argv) < 3:
            print("Usage: python crypto.py check <address>")
            sys.exit(1)

        address = sys.argv[2]
        print(f"Checking wallet: {address[:8]}...{address[-4:]}")

        try:
            total, positions = get_wallet_value(address)
            print(f"\nTotal Value: ${total:,.2f}")
            print("\nTop Positions:")
            for pos in positions[:10]:
                print(f"  {pos['symbol']}: {pos['quantity']:.4f} (${pos['value_usd']:,.2f})")
        except Exception as e:
            print(f"❌ Error: {e}")

    elif command == 'chains':
        print("Supported blockchains:")
        for chain in get_supported_chains():
            print(f"  • {chain}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
