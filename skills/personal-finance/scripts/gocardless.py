#!/usr/bin/env python3
"""
GoCardless Bank Account Data API Client

DEPRECATED: This module is deprecated. Use enablebanking.py instead.

GoCardless is no longer accepting new applications for their Bank Account Data API.
The Enable Banking API (enablebanking.py) is the recommended replacement.

This file is kept for backwards compatibility with existing installations.
"""

import warnings
warnings.warn(
    "gocardless.py is deprecated. Use enablebanking.py instead. "
    "GoCardless is no longer accepting new API applications.",
    DeprecationWarning,
    stacklevel=2
)

import os
import json
import time
import logging
import requests
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

try:
    from config import API_TIMEOUT_SECONDS, CREDENTIAL_FILE_PERMISSIONS
except ImportError:
    API_TIMEOUT_SECONDS = 60
    CREDENTIAL_FILE_PERMISSIONS = 0o600

# Set up logger
logger = logging.getLogger(__name__)

# Default redirect URL - can be overridden with GOCARDLESS_REDIRECT_URL env var
DEFAULT_REDIRECT_URL = os.environ.get('GOCARDLESS_REDIRECT_URL', 'http://localhost:8080/callback')

# Try to import keychain helper
try:
    import sys
    sys.path.append(str(Path.home() / '.config' / 'clawdbot'))
    from keychain import get_key, set_key
    KEYCHAIN_AVAILABLE = True
except ImportError:
    KEYCHAIN_AVAILABLE = False
    logger.warning("Keychain not available, falling back to file storage")

class GoCardlessClient:
    """GoCardless Bank Account Data API Client"""
    
    BASE_URL = "https://bankaccountdata.gocardless.com/api/v2"
    
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self._setup_session()
        
    def _setup_session(self):
        """Setup session with headers and timeout"""
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Clawdbot-Finance/1.0'
        })
        self.session.timeout = API_TIMEOUT_SECONDS
        
    def _get_user_secrets(self) -> Tuple[str, str]:
        """Get secret_id and secret_key from storage"""
        if KEYCHAIN_AVAILABLE:
            secret_id = get_key('gocardless_secret_id')
            secret_key = get_key('gocardless_secret_key') 
        else:
            # Fallback to file storage (for development)
            creds_file = Path.home() / '.config' / 'gocardless_creds.json'
            if creds_file.exists():
                with open(creds_file) as f:
                    creds = json.load(f)
                    secret_id = creds.get('secret_id')
                    secret_key = creds.get('secret_key')
            else:
                secret_id = secret_key = None
                
        if not secret_id or not secret_key:
            raise ValueError("GoCardless credentials not found. Run setup first.")
            
        return secret_id, secret_key
        
    def _get_access_token(self) -> str:
        """Get valid access token, refresh if needed"""
        # Try to get existing token
        if KEYCHAIN_AVAILABLE:
            token = get_key('gocardless_access_token')
            expires_str = get_key('gocardless_access_expires')
        else:
            # File fallback
            token_file = Path.home() / '.config' / 'gocardless_token.json'
            if token_file.exists():
                with open(token_file) as f:
                    data = json.load(f)
                    token = data.get('access_token')
                    expires_str = data.get('expires_at')
            else:
                token = expires_str = None
                
        # Check if token is still valid
        if token and expires_str:
            expires_at = datetime.fromisoformat(expires_str)
            if datetime.now() < expires_at - timedelta(minutes=5):  # 5min buffer
                return token
                
        # Need to refresh or get new token
        return self._refresh_access_token()
        
    def _refresh_access_token(self) -> str:
        """Get new access token using refresh token or secrets"""
        # Try refresh token first
        if KEYCHAIN_AVAILABLE:
            refresh_token = get_key('gocardless_refresh_token')
            refresh_expires = get_key('gocardless_refresh_expires')
        else:
            token_file = Path.home() / '.config' / 'gocardless_token.json'
            if token_file.exists():
                with open(token_file) as f:
                    data = json.load(f)
                    refresh_token = data.get('refresh_token')
                    refresh_expires = data.get('refresh_expires_at')
            else:
                refresh_token = refresh_expires = None
                
        # Check if refresh token is valid
        if refresh_token and refresh_expires:
            expires_at = datetime.fromisoformat(refresh_expires)
            if datetime.now() < expires_at:
                # Use refresh token
                response = self.session.post(f"{self.BASE_URL}/token/refresh/", 
                                           json={'refresh': refresh_token})
                if response.status_code == 200:
                    data = response.json()
                    access_token = data['access']
                    expires_at = datetime.now() + timedelta(seconds=data.get('access_expires', 86400))
                    
                    # Store new access token
                    self._store_token(access_token, expires_at.isoformat(), refresh_token, refresh_expires)
                    return access_token
                    
        # Fallback to creating new tokens from secrets
        return self._create_new_tokens()
        
    def _create_new_tokens(self) -> str:
        """Create new refresh and access tokens from user secrets"""
        secret_id, secret_key = self._get_user_secrets()
        
        # Create refresh token
        response = self.session.post(f"{self.BASE_URL}/token/new/", 
                                   json={'secret_id': secret_id, 'secret_key': secret_key})
        
        if response.status_code != 200:
            raise Exception(f"Failed to create tokens: {response.status_code} {response.text}")
            
        data = response.json()
        refresh_token = data['refresh']
        refresh_expires_at = datetime.now() + timedelta(days=30)  # 30 days
        
        # Get access token
        response = self.session.post(f"{self.BASE_URL}/token/refresh/", 
                                   json={'refresh': refresh_token})
        
        if response.status_code != 200:
            raise Exception(f"Failed to get access token: {response.status_code} {response.text}")
            
        data = response.json()
        access_token = data['access']
        access_expires_at = datetime.now() + timedelta(seconds=data.get('access_expires', 86400))
        
        # Store both tokens
        self._store_token(access_token, access_expires_at.isoformat(), 
                         refresh_token, refresh_expires_at.isoformat())
        
        return access_token
        
    def _store_token(self, access_token: str, access_expires: str, 
                    refresh_token: str, refresh_expires: str):
        """Store tokens securely"""
        if KEYCHAIN_AVAILABLE:
            set_key('gocardless_access_token', access_token)
            set_key('gocardless_access_expires', access_expires)
            set_key('gocardless_refresh_token', refresh_token)
            set_key('gocardless_refresh_expires', refresh_expires)
        else:
            # File fallback
            token_file = Path.home() / '.config' / 'gocardless_token.json'
            token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(token_file, 'w') as f:
                json.dump({
                    'access_token': access_token,
                    'expires_at': access_expires,
                    'refresh_token': refresh_token,
                    'refresh_expires_at': refresh_expires
                }, f)
            # Set restrictive permissions (owner read/write only)
            os.chmod(token_file, CREDENTIAL_FILE_PERMISSIONS)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make authenticated API request with rate limit handling"""
        if not self.access_token:
            self.access_token = self._get_access_token()
            
        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f'Bearer {self.access_token}'
        
        url = f"{self.BASE_URL}{endpoint}"
        
        response = self.session.request(method, url, headers=headers, **kwargs)
        
        # Handle rate limits
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            raise RateLimitError(f"Rate limited. Retry after {retry_after} seconds.", retry_after)
            
        # Handle token expiry
        if response.status_code == 401:
            # Try refreshing token once
            self.access_token = self._refresh_access_token()
            headers['Authorization'] = f'Bearer {self.access_token}'
            response = self.session.request(method, url, headers=headers, **kwargs)
            
        if response.status_code >= 400:
            raise APIError(f"API Error {response.status_code}: {response.text}")
            
        return response.json()
        
    def list_institutions(self, country: str = 'CH') -> List[Dict]:
        """Get list of supported banks for country"""
        return self._make_request('GET', f'/institutions/?country={country}')
        
    def create_agreement(self, institution_id: str, max_historical_days: int = 90,
                        access_valid_for_days: int = 90) -> Dict:
        """Create end-user agreement"""
        data = {
            'institution_id': institution_id,
            'max_historical_days': max_historical_days,
            'access_valid_for_days': access_valid_for_days,
            'access_scope': ['balances', 'details', 'transactions']
        }
        return self._make_request('POST', '/agreements/enduser/', json=data)
        
    def create_requisition(self, institution_id: str, redirect_url: str = None,
                          agreement_id: Optional[str] = None) -> Dict:
        """Create bank connection requisition"""
        if redirect_url is None:
            redirect_url = DEFAULT_REDIRECT_URL

        data = {
            'redirect': redirect_url,
            'institution_id': institution_id,
            'reference': f"clawdbot-{int(time.time())}"
        }
        if agreement_id:
            data['agreement'] = agreement_id
            
        return self._make_request('POST', '/requisitions/', json=data)
        
    def get_requisition(self, requisition_id: str) -> Dict:
        """Get requisition status and accounts"""
        return self._make_request('GET', f'/requisitions/{requisition_id}/')
        
    def get_account_details(self, account_id: str) -> Dict:
        """Get account holder information and IBAN"""
        return self._make_request('GET', f'/accounts/{account_id}/details/')
        
    def get_account_balances(self, account_id: str) -> Dict:
        """Get current account balances"""
        return self._make_request('GET', f'/accounts/{account_id}/balances/')
        
    def get_account_transactions(self, account_id: str, date_from: str = None,
                               date_to: str = None) -> Dict:
        """Get account transactions"""
        params = {}
        if date_from:
            params['date_from'] = date_from
        if date_to:
            params['date_to'] = date_to
            
        return self._make_request('GET', f'/accounts/{account_id}/transactions/', params=params)

def setup_bank_connection(client: GoCardlessClient, country: str = 'CH') -> Dict:
    """Interactive bank connection setup"""
    try:
        # List available institutions
        print("🔍 Fetching available banks...")
        institutions = client.list_institutions(country)
        
        if not institutions:
            return {'success': False, 'error': f'No banks found for country {country}'}
            
        # Show popular banks first
        popular_banks = ['UBS', 'Credit Suisse', 'PostFinance', 'Raiffeisen', 'ZKB']
        popular_institutions = []
        other_institutions = []
        
        for inst in institutions:
            name = inst.get('name', '')
            if any(bank.lower() in name.lower() for bank in popular_banks):
                popular_institutions.append(inst)
            else:
                other_institutions.append(inst)
                
        # Display options
        print(f"\n🏦 Popular banks in {country}:")
        for i, inst in enumerate(popular_institutions[:10]):  # Show top 10
            print(f"  {i+1}. {inst['name']}")
            
        if other_institutions:
            print(f"\n💡 {len(other_institutions)} other banks available")
            print("   (Use full institution list if your bank is not above)")
            
        # For MVP, auto-select first available or sandbox
        sandbox_inst = next((inst for inst in institutions if 'sandbox' in inst['name'].lower()), None)
        if sandbox_inst:
            selected_institution = sandbox_inst
            print(f"\n🧪 Using sandbox for testing: {selected_institution['name']}")
        else:
            selected_institution = popular_institutions[0] if popular_institutions else institutions[0]
            print(f"\n🎯 Auto-selecting: {selected_institution['name']}")
            print("   (In production, user would choose from list)")
            
        # Create agreement
        print("📝 Creating end-user agreement...")
        agreement = client.create_agreement(selected_institution['id'])
        
        # Create requisition
        print("🔗 Creating bank connection...")
        requisition = client.create_requisition(
            selected_institution['id'],
            agreement_id=agreement['id']
        )
        
        # Store requisition info
        from db import store_requisition
        store_requisition(requisition, selected_institution)
        
        return {
            'success': True,
            'requisition_id': requisition['id'],
            'auth_url': requisition['link'],
            'institution': selected_institution['name']
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def check_and_update_accounts():
    """Check requisition status and update account list"""
    from db import get_pending_requisitions, store_accounts
    
    client = GoCardlessClient()
    requisitions = get_pending_requisitions()
    
    for req in requisitions:
        try:
            status = client.get_requisition(req['id'])
            if status['status'] == 'LN':  # Linked
                # Get accounts
                accounts = status.get('accounts', [])
                for account_id in accounts:
                    # Fetch account details
                    details = client.get_account_details(account_id)
                    store_accounts(req['id'], account_id, details, req['institution_name'])
                    
                print(f"✅ Connected {len(accounts)} accounts from {req['institution_name']}")
                
        except Exception as e:
            print(f"❌ Error checking requisition {req['id']}: {e}")

class APIError(Exception):
    """API request error"""
    pass

class RateLimitError(Exception):
    """Rate limit exceeded"""
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after

def setup_credentials():
    """Interactive credential setup"""
    print("🔧 GoCardless Bank Account Data Setup")
    print("=" * 50)
    print("1. Go to https://bankaccountdata.gocardless.com/user-secrets/")
    print("2. Create a new secret (free tier is fine)")
    print("3. Copy the secret_id and secret_key")
    print()

    secret_id = input("Enter your secret_id: ").strip()
    secret_key = input("Enter your secret_key: ").strip()

    if not secret_id or not secret_key:
        print("❌ Both secret_id and secret_key are required")
        return False

    try:
        if KEYCHAIN_AVAILABLE:
            set_key('gocardless_secret_id', secret_id)
            set_key('gocardless_secret_key', secret_key)
            print("✅ Credentials saved to keychain")
        else:
            # File fallback
            creds_file = Path.home() / '.config' / 'gocardless_creds.json'
            creds_file.parent.mkdir(parents=True, exist_ok=True)
            with open(creds_file, 'w') as f:
                json.dump({'secret_id': secret_id, 'secret_key': secret_key}, f)
            # Set restrictive permissions (owner read/write only)
            os.chmod(creds_file, CREDENTIAL_FILE_PERMISSIONS)
            print(f"✅ Credentials saved to {creds_file}")

        # Test the credentials
        client = GoCardlessClient()
        institutions = client.list_institutions('CH')
        print(f"🎉 Success! Found {len(institutions)} Swiss banks")
        return True

    except Exception as e:
        print(f"❌ Error saving credentials: {e}")
        return False


def setup_credentials_programmatic(secret_id: str, secret_key: str, test_country: str = 'CH') -> bool:
    """
    Save GoCardless credentials programmatically (without interactive prompts)

    Args:
        secret_id: GoCardless secret_id
        secret_key: GoCardless secret_key
        test_country: Country code to test API call (default: CH)

    Returns:
        True if credentials saved and validated successfully, False otherwise
    """
    if not secret_id or not secret_key:
        logger.error("Both secret_id and secret_key are required")
        return False

    try:
        if KEYCHAIN_AVAILABLE:
            set_key('gocardless_secret_id', secret_id)
            set_key('gocardless_secret_key', secret_key)
            logger.info("Credentials saved to keychain")
        else:
            # File fallback
            creds_file = Path.home() / '.config' / 'gocardless_creds.json'
            creds_file.parent.mkdir(parents=True, exist_ok=True)
            with open(creds_file, 'w') as f:
                json.dump({'secret_id': secret_id, 'secret_key': secret_key}, f)
            # Set restrictive permissions (owner read/write only)
            os.chmod(creds_file, CREDENTIAL_FILE_PERMISSIONS)
            logger.info(f"Credentials saved to {creds_file}")

        # Test the credentials by making a simple API call
        client = GoCardlessClient()
        institutions = client.list_institutions(test_country)
        logger.info(f"Credentials verified - found {len(institutions)} banks for {test_country}")
        return True

    except Exception as e:
        logger.error(f"Error saving/validating credentials: {e}")
        return False

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'setup':
        setup_credentials()
    else:
        print("Usage: python gocardless.py setup")