#!/usr/bin/env python3
"""
Enable Banking API Client

Provides secure access to European bank accounts via the Enable Banking Open Banking API.
Handles JWT authentication, session management, and account data retrieval.

API Documentation: https://enablebanking.com/docs/api/reference/
"""

import os
import json
import logging
import uuid
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

try:
    import jwt as pyjwt
except ImportError:
    raise ImportError("PyJWT is required. Install with: pip install pyjwt")

try:
    from config import API_TIMEOUT_SECONDS, CREDENTIAL_FILE_PERMISSIONS
except ImportError:
    API_TIMEOUT_SECONDS = 60
    CREDENTIAL_FILE_PERMISSIONS = 0o600

# Set up logger
logger = logging.getLogger(__name__)

# Default redirect URL - can be overridden with ENABLE_BANKING_REDIRECT_URL env var
DEFAULT_REDIRECT_URL = os.environ.get(
    'ENABLE_BANKING_REDIRECT_URL',
    'http://localhost:8080/callback'
)

# Try to import keychain helper for secure credential storage
KEYCHAIN_AVAILABLE = False
get_key = None
set_key = None

try:
    import sys
    sys.path.append(str(Path.home() / '.config' / 'clawdbot'))
    from keychain import get_key, set_key
    KEYCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("Keychain not available, falling back to file storage")


class EnableBankingClient:
    """
    Enable Banking API Client

    Provides methods for interacting with the Enable Banking Open Banking API,
    including bank discovery, authorization, and account data retrieval.

    Authentication uses JWT tokens signed with RS256 algorithm.

    Example:
        client = EnableBankingClient()
        banks = client.list_institutions('CH')
        auth = client.start_authorization('UBS', 'CH')
    """

    BASE_URL = "https://api.enablebanking.com"
    JWT_VALIDITY_SECONDS = 3600  # 1 hour
    JWT_REFRESH_BUFFER_MINUTES = 5

    def __init__(self):
        """Initialize the client with a requests session."""
        self.session = requests.Session()
        self._jwt_token: Optional[str] = None
        self._jwt_expires_at: Optional[datetime] = None
        self._setup_session()

    def _setup_session(self) -> None:
        """Configure session with default headers and timeout."""
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Clawdbot-Finance/1.0'
        })

    def _get_credentials(self) -> Tuple[str, str]:
        """
        Retrieve application credentials from secure storage.

        Checks keychain first, then falls back to file storage.

        Returns:
            Tuple of (application_id, private_key)

        Raises:
            ValueError: If credentials are not found
        """
        application_id = None
        private_key = None

        if KEYCHAIN_AVAILABLE and get_key is not None:
            application_id = get_key('enablebanking_application_id')
            private_key = get_key('enablebanking_private_key')

        # Fallback to file storage
        if not application_id or not private_key:
            creds_file = Path.home() / '.config' / 'enablebanking_creds.json'
            if creds_file.exists():
                with open(creds_file, 'r', encoding='utf-8') as f:
                    creds = json.load(f)
                    application_id = creds.get('application_id')
                    private_key = creds.get('private_key')

        # Check for separate private key file
        if application_id and not private_key:
            key_file = Path.home() / '.config' / 'enablebanking' / f'{application_id}.pem'
            if key_file.exists():
                with open(key_file, 'r', encoding='utf-8') as f:
                    private_key = f.read()

        if not application_id or not private_key:
            raise ValueError(
                "Enable Banking credentials not found. "
                "Run 'python enablebanking.py setup' first."
            )

        return application_id, private_key

    def _get_jwt_token(self) -> str:
        """
        Get a valid JWT token, regenerating if expired or missing.

        Returns:
            Valid JWT token string
        """
        # Check if existing token is still valid (with buffer for clock skew)
        if self._jwt_token and self._jwt_expires_at:
            buffer = timedelta(minutes=self.JWT_REFRESH_BUFFER_MINUTES)
            if datetime.now() < self._jwt_expires_at - buffer:
                return self._jwt_token

        # Generate new JWT token
        return self._generate_jwt_token()

    def _generate_jwt_token(self) -> str:
        """
        Generate a new JWT token for API authentication.

        The token is signed with RS256 using the private key from credentials.

        Returns:
            Newly generated JWT token string
        """
        application_id, private_key = self._get_credentials()

        now = datetime.now(timezone.utc)
        iat = int(now.timestamp())
        exp = iat + self.JWT_VALIDITY_SECONDS

        jwt_body = {
            "iss": "enablebanking.com",
            "aud": "api.enablebanking.com",
            "iat": iat,
            "exp": exp,
        }

        self._jwt_token = pyjwt.encode(
            jwt_body,
            private_key,
            algorithm="RS256",
            headers={"kid": application_id},
        )
        self._jwt_expires_at = datetime.fromtimestamp(exp)

        return self._jwt_token

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Make an authenticated API request with automatic retry on auth failure.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint path (e.g., '/aspsps')
            **kwargs: Additional arguments passed to requests

        Returns:
            Parsed JSON response as dictionary

        Raises:
            RateLimitError: If API rate limit is exceeded
            APIError: If API returns an error response
        """
        jwt_token = self._get_jwt_token()

        headers = kwargs.pop('headers', {})
        headers['Authorization'] = f'Bearer {jwt_token}'

        url = f"{self.BASE_URL}{endpoint}"

        response = self.session.request(
            method, url, headers=headers, timeout=API_TIMEOUT_SECONDS, **kwargs
        )

        # Handle rate limits
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            raise RateLimitError(
                f"Rate limited. Retry after {retry_after} seconds.",
                retry_after
            )

        # Handle authentication errors - retry once with fresh token
        if response.status_code == 401:
            self._jwt_token = None
            jwt_token = self._get_jwt_token()
            headers['Authorization'] = f'Bearer {jwt_token}'
            response = self.session.request(
                method, url, headers=headers, timeout=API_TIMEOUT_SECONDS, **kwargs
            )

        if response.status_code >= 400:
            raise APIError(f"API Error {response.status_code}: {response.text}")

        return response.json()

    def get_application(self) -> Dict:
        """
        Get application details.

        Returns:
            Application information including name, environment, and redirect URLs
        """
        return self._make_request('GET', '/application')

    def list_institutions(self, country: str = 'CH') -> List[Dict]:
        """
        Get list of supported banks (ASPSPs) for a country.

        Args:
            country: Two-letter ISO 3166 country code (e.g., 'CH', 'DE', 'GB')

        Returns:
            List of institution dictionaries with name, country, and capabilities
        """
        response = self._make_request('GET', f'/aspsps?country={country}')
        return response.get('aspsps', [])

    def start_authorization(
        self,
        institution_name: str,
        country: str = 'CH',
        redirect_url: Optional[str] = None,
        valid_days: int = 90,
        psu_type: str = 'personal'
    ) -> Dict:
        """
        Start the authorization flow for bank connection.

        Args:
            institution_name: Name of the bank/ASPSP
            country: Two-letter ISO country code
            redirect_url: URL to redirect user after bank auth (default: localhost)
            valid_days: Number of days the access consent is valid
            psu_type: Type of user - 'personal' or 'business'

        Returns:
            Dict containing 'url' for user to authenticate with their bank
        """
        if redirect_url is None:
            redirect_url = DEFAULT_REDIRECT_URL

        valid_until = datetime.now(timezone.utc) + timedelta(days=valid_days)

        body = {
            "access": {
                "valid_until": valid_until.isoformat(),
                "balances": True,
                "transactions": True
            },
            "aspsp": {
                "name": institution_name,
                "country": country
            },
            "state": str(uuid.uuid4()),
            "redirect_url": redirect_url,
            "psu_type": psu_type,
        }

        return self._make_request('POST', '/auth', json=body)

    def create_session(self, auth_code: str) -> Dict:
        """
        Create a session after user completes bank authorization.

        Args:
            auth_code: Authorization code from redirect URL query params

        Returns:
            Session data including session_id and list of accounts
        """
        return self._make_request('POST', '/sessions', json={"code": auth_code})

    def get_session(self, session_id: str) -> Dict:
        """
        Get session details and current status.

        Args:
            session_id: The session identifier

        Returns:
            Session information including accounts and validity
        """
        return self._make_request('GET', f'/sessions/{session_id}')

    def delete_session(self, session_id: str) -> Dict:
        """
        Delete a session and revoke the user's consent.

        Args:
            session_id: The session identifier to delete

        Returns:
            Confirmation of deletion
        """
        return self._make_request('DELETE', f'/sessions/{session_id}')

    def get_account_details(self, account_uid: str) -> Dict:
        """
        Get account holder information.

        Args:
            account_uid: Unique account identifier from session

        Returns:
            Account details including IBAN, holder name, and type
        """
        return self._make_request('GET', f'/accounts/{account_uid}/details')

    def get_account_balances(self, account_uid: str) -> Dict:
        """
        Get current account balances.

        Args:
            account_uid: Unique account identifier from session

        Returns:
            Balance information including available and booked amounts
        """
        return self._make_request('GET', f'/accounts/{account_uid}/balances')

    def get_account_transactions(
        self,
        account_uid: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> Dict:
        """
        Get account transactions with automatic pagination handling.

        Args:
            account_uid: Unique account identifier from session
            date_from: Start date in ISO format (YYYY-MM-DD)
            date_to: End date in ISO format (YYYY-MM-DD)

        Returns:
            Dict with 'transactions' key containing 'booked' transactions list
        """
        params: Dict[str, str] = {}
        if date_from:
            params['date_from'] = date_from
        if date_to:
            params['date_to'] = date_to

        all_transactions: List[Dict] = []
        continuation_key: Optional[str] = None

        while True:
            if continuation_key:
                params['continuation_key'] = continuation_key

            response = self._make_request(
                'GET',
                f'/accounts/{account_uid}/transactions',
                params=params
            )

            transactions = response.get('transactions', [])
            all_transactions.extend(transactions)

            continuation_key = response.get('continuation_key')
            if not continuation_key:
                break

        # Return in format compatible with existing code expecting GoCardless structure
        return {'transactions': {'booked': all_transactions}}


def setup_bank_connection(client: EnableBankingClient, country: str = 'CH') -> Dict:
    """
    Interactive bank connection setup with institution selection.

    Fetches available banks for the specified country, displays options,
    and initiates the authorization flow.

    Args:
        client: Initialized EnableBankingClient instance
        country: Two-letter ISO country code (default: 'CH' for Switzerland)

    Returns:
        Dict with keys:
            - success: bool indicating if setup started successfully
            - auth_url: URL for user to authenticate (if success)
            - state: State parameter for CSRF protection (if success)
            - institution: Selected bank name (if success)
            - error: Error message (if not success)
    """
    try:
        # List available institutions
        print("Fetching available banks...")
        institutions = client.list_institutions(country)

        if not institutions:
            return {
                'success': False,
                'error': f'No banks found for country {country}'
            }

        # Categorize banks - popular ones first for better UX
        popular_bank_names = ['UBS', 'Credit Suisse', 'PostFinance', 'Raiffeisen', 'ZKB']
        popular_institutions = []
        other_institutions = []
        sandbox_inst = None

        for inst in institutions:
            name = inst.get('name', '')
            if 'sandbox' in name.lower():
                sandbox_inst = inst
            elif any(bank.lower() in name.lower() for bank in popular_bank_names):
                popular_institutions.append(inst)
            else:
                other_institutions.append(inst)

        # Build display list (popular first, then others)
        display_list = popular_institutions + other_institutions

        # Display options
        print(f"\n🏦 Available banks in {country}:")
        print()

        # Show popular banks
        if popular_institutions:
            print("Popular:")
            for i, inst in enumerate(popular_institutions, 1):
                print(f"  {i}. {inst['name']}")
            print()

        # Show count of other banks
        if other_institutions:
            start_idx = len(popular_institutions) + 1
            print(f"Other banks: {len(other_institutions)} more available")
            print(f"  (Enter 'list' to see all, or enter {start_idx}-{len(display_list)} to select)")
            print()

        # Show sandbox option
        if sandbox_inst:
            print("🧪 Sandbox: Enter 's' to use sandbox for testing")
            print()

        # Interactive selection loop
        selected_institution = None
        while selected_institution is None:
            choice = input("Enter bank number (or 's' for sandbox, 'list' for all): ").strip().lower()

            if choice == 's' and sandbox_inst:
                selected_institution = sandbox_inst
                print(f"\n✅ Selected: {selected_institution['name']}")

            elif choice == 'list':
                # Show full list
                print(f"\n📋 All {len(display_list)} banks in {country}:")
                for i, inst in enumerate(display_list, 1):
                    print(f"  {i}. {inst['name']}")
                print()

            elif choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(display_list):
                    selected_institution = display_list[idx - 1]
                    print(f"\n✅ Selected: {selected_institution['name']}")
                else:
                    print(f"❌ Invalid number. Enter 1-{len(display_list)}")

            elif choice == 'q' or choice == 'quit':
                return {'success': False, 'error': 'User cancelled'}

            else:
                print("❌ Invalid input. Enter a number, 's' for sandbox, or 'list' to see all banks.")

        # Start authorization
        print("\n🔗 Starting bank authorization...")
        auth_response = client.start_authorization(
            selected_institution['name'],
            country
        )

        return {
            'success': True,
            'auth_url': auth_response['url'],
            'state': auth_response.get('state'),
            'institution': selected_institution['name']
        }

    except APIError as e:
        logger.error(f"API error during bank connection setup: {e}")
        return {'success': False, 'error': str(e)}
    except Exception as e:
        logger.exception("Unexpected error during bank connection setup")
        return {'success': False, 'error': str(e)}


def complete_authorization(client: EnableBankingClient, redirected_url: str) -> Dict:
    """
    Complete the authorization flow after user is redirected back from bank.

    Parses the authorization code from the redirect URL and creates a session
    to access the user's bank accounts.

    Args:
        client: Initialized EnableBankingClient instance
        redirected_url: The full URL the user was redirected to after bank auth

    Returns:
        Dict with keys:
            - success: bool indicating if authorization completed
            - session_id: Session identifier for future API calls (if success)
            - accounts: List of connected account objects (if success)
            - error: Error message (if not success)
    """
    try:
        # Parse auth code from redirect URL
        parsed = urlparse(redirected_url)
        query_params = parse_qs(parsed.query)

        # Check for error response from bank
        if 'error' in query_params:
            error_desc = query_params.get('error_description', ['Authorization failed'])
            error_msg = error_desc[0] if error_desc else 'Authorization failed'
            return {'success': False, 'error': error_msg}

        # Extract authorization code
        if 'code' not in query_params:
            return {
                'success': False,
                'error': 'No authorization code in redirect URL. '
                         'Please ensure you copied the complete URL.'
            }

        auth_code = query_params['code'][0]

        # Create session with the auth code
        session = client.create_session(auth_code)

        # Store session and accounts in database
        try:
            from db import store_session, store_accounts
            store_session(session)

            accounts = session.get('accounts', [])
            for account in accounts:
                store_accounts(session['session_id'], account)
        except ImportError:
            logger.warning("Database module not available, session not persisted")
            accounts = session.get('accounts', [])

        print(f"✅ Connected {len(accounts)} account(s)")

        return {
            'success': True,
            'session_id': session['session_id'],
            'accounts': accounts
        }

    except APIError as e:
        logger.error(f"API error completing authorization: {e}")
        return {'success': False, 'error': str(e)}
    except Exception as e:
        logger.exception("Unexpected error completing authorization")
        return {'success': False, 'error': str(e)}


def check_and_update_accounts() -> None:
    """
    Check all active sessions and update account information.

    Iterates through stored sessions, fetches current account data
    from Enable Banking, and updates the local database.
    """
    try:
        from db import get_active_sessions, store_accounts
    except ImportError:
        logger.error("Database module not available")
        return

    client = EnableBankingClient()
    sessions = get_active_sessions()

    if not sessions:
        print("No active sessions found.")
        return

    for sess in sessions:
        session_id = sess.get('session_id', '')
        try:
            session_data = client.get_session(session_id)

            # Update accounts
            accounts = session_data.get('accounts', [])
            for account in accounts:
                store_accounts(session_id, account)

            session_preview = session_id[:8] if len(session_id) > 8 else session_id
            print(f"✅ Updated {len(accounts)} account(s) from session {session_preview}...")

        except APIError as e:
            logger.error(f"API error checking session {session_id}: {e}")
            print(f"❌ Error checking session {session_id[:8]}...: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error checking session {session_id}")
            print(f"❌ Error checking session {session_id[:8]}...: {e}")


# =============================================================================
# Exception Classes
# =============================================================================

class APIError(Exception):
    """
    Exception raised when the Enable Banking API returns an error response.

    Attributes:
        message: Human-readable error description
    """
    pass


class RateLimitError(APIError):
    """
    Exception raised when API rate limit is exceeded.

    Attributes:
        message: Human-readable error description
        retry_after: Number of seconds to wait before retrying
    """

    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


def setup_credentials() -> bool:
    """
    Interactive credential setup wizard.

    Guides the user through setting up Enable Banking API credentials,
    validates them, and stores them securely.

    Returns:
        True if setup completed successfully, False otherwise
    """
    print("🔧 Enable Banking Setup")
    print("=" * 50)
    print()
    print("To get started, you'll need Enable Banking credentials:")
    print()
    print("1. Go to https://enablebanking.com/sign-in/")
    print("2. Sign in with your email (new accounts auto-created)")
    print("3. Navigate to 'API applications' in the Control Panel")
    print("4. Register a new application")
    print("5. Download the private key file (.pem)")
    print("6. Copy your Application ID")
    print()

    application_id = input("Enter your Application ID: ").strip()
    if not application_id:
        print("❌ Application ID is required")
        return False

    print()
    print("For the private key, you can either:")
    print("  a) Provide the path to your .pem file")
    print("  b) Paste the key content directly (starts with -----BEGIN)")
    print()

    key_input = input("Enter private key path or content: ").strip()

    # Determine if input is a file path or direct key content
    private_key = None
    if os.path.exists(key_input):
        try:
            with open(key_input, 'r', encoding='utf-8') as f:
                private_key = f.read()
            print(f"✅ Read private key from {key_input}")
        except IOError as e:
            print(f"❌ Could not read file: {e}")
            return False
    elif key_input.startswith('-----BEGIN'):
        private_key = key_input
    else:
        print("❌ Invalid input. Expected a file path or PEM-formatted key.")
        return False

    if not private_key:
        print("❌ Private key is required")
        return False

    # Validate key format
    if '-----BEGIN' not in private_key or '-----END' not in private_key:
        print("❌ Invalid private key format. Expected PEM format.")
        return False

    try:
        # Save credentials
        if KEYCHAIN_AVAILABLE and set_key is not None:
            set_key('enablebanking_application_id', application_id)
            set_key('enablebanking_private_key', private_key)
            print("✅ Credentials saved to keychain")
        else:
            # File fallback with secure permissions
            creds_dir = Path.home() / '.config' / 'enablebanking'
            creds_dir.mkdir(parents=True, exist_ok=True)

            creds_file = Path.home() / '.config' / 'enablebanking_creds.json'
            with open(creds_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'application_id': application_id,
                    'private_key': private_key
                }, f)
            os.chmod(creds_file, CREDENTIAL_FILE_PERMISSIONS)

            # Also save key file separately for tools that need it
            key_file = creds_dir / f'{application_id}.pem'
            with open(key_file, 'w', encoding='utf-8') as f:
                f.write(private_key)
            os.chmod(key_file, CREDENTIAL_FILE_PERMISSIONS)

            print(f"✅ Credentials saved to {creds_file}")

        # Test the credentials
        print()
        print("🔍 Validating credentials...")
        client = EnableBankingClient()
        app_info = client.get_application()
        institutions = client.list_institutions('CH')

        app_name = app_info.get('name', 'Unknown')
        print(f"✅ Success! Connected to app: {app_name}")
        print(f"✅ Found {len(institutions)} Swiss banks available")
        return True

    except APIError as e:
        print(f"❌ API error: {e}")
        print("   Please verify your credentials and try again.")
        return False
    except Exception as e:
        logger.exception("Error during credential setup")
        print(f"❌ Error: {e}")
        return False


def setup_credentials_programmatic(
    application_id: str,
    private_key: str,
    test_country: str = 'CH'
) -> bool:
    """
    Save Enable Banking credentials programmatically.

    Use this function for automated setup without interactive prompts.

    Args:
        application_id: Enable Banking application ID
        private_key: Private key content in PEM format
        test_country: Country code to test API call (default: 'CH')

    Returns:
        True if credentials were saved and validated successfully

    Example:
        with open('my_key.pem') as f:
            key = f.read()
        success = setup_credentials_programmatic('app_123', key)
    """
    if not application_id:
        logger.error("Application ID is required")
        return False

    if not private_key:
        logger.error("Private key is required")
        return False

    # Basic validation of private key format
    if '-----BEGIN' not in private_key:
        logger.error("Invalid private key format - expected PEM format")
        return False

    try:
        # Save credentials
        if KEYCHAIN_AVAILABLE and set_key is not None:
            set_key('enablebanking_application_id', application_id)
            set_key('enablebanking_private_key', private_key)
            logger.info("Credentials saved to keychain")
        else:
            # File fallback with secure permissions
            creds_dir = Path.home() / '.config' / 'enablebanking'
            creds_dir.mkdir(parents=True, exist_ok=True)

            creds_file = Path.home() / '.config' / 'enablebanking_creds.json'
            with open(creds_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'application_id': application_id,
                    'private_key': private_key
                }, f)
            os.chmod(creds_file, CREDENTIAL_FILE_PERMISSIONS)
            logger.info(f"Credentials saved to {creds_file}")

        # Validate credentials by making a test API call
        client = EnableBankingClient()
        institutions = client.list_institutions(test_country)
        logger.info(
            f"Credentials verified - found {len(institutions)} banks for {test_country}"
        )
        return True

    except APIError as e:
        logger.error(f"API error validating credentials: {e}")
        return False
    except Exception as e:
        logger.exception(f"Error saving/validating credentials: {e}")
        return False


# =============================================================================
# Backwards Compatibility
# =============================================================================

# Alias for migration from GoCardless - allows existing code to work unchanged
GoCardlessClient = EnableBankingClient


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'setup':
        success = setup_credentials()
        sys.exit(0 if success else 1)
    else:
        print("Enable Banking API Client")
        print()
        print("Usage:")
        print("  python enablebanking.py setup    - Interactive credential setup")
        print()
        print("For programmatic usage, import and use EnableBankingClient:")
        print("  from enablebanking import EnableBankingClient")
        print("  client = EnableBankingClient()")
        print("  banks = client.list_institutions('CH')")
