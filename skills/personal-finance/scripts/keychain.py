#!/usr/bin/env python3
"""
macOS Keychain helper for secure credential storage.

Usage:
    # As a module
    import keychain
    keychain.set("api_key", "secret_value")
    value = keychain.get("api_key")
    keychain.delete("api_key")
    
    # As CLI
    python3 keychain.py get notion_api_key
    python3 keychain.py set notion_api_key "your-key"
    python3 keychain.py delete notion_api_key
    python3 keychain.py list
"""

import subprocess
import sys
import os

# Service name for all keys
SERVICE = os.environ.get("KEYCHAIN_SERVICE", "financial-skill")


def get(key: str) -> str | None:
    """Retrieve a value from the keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", SERVICE, "-a", key, "-w"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


def set(key: str, value: str) -> bool:
    """Store a value in the keychain."""
    try:
        # Delete existing entry first (ignore errors)
        subprocess.run(
            ["security", "delete-generic-password", "-s", SERVICE, "-a", key],
            capture_output=True
        )
        
        # Add new entry
        result = subprocess.run(
            ["security", "add-generic-password", "-s", SERVICE, "-a", key, "-w", value],
            capture_output=True
        )
        return result.returncode == 0
    except Exception:
        return False


def delete(key: str) -> bool:
    """Delete a value from the keychain."""
    try:
        result = subprocess.run(
            ["security", "delete-generic-password", "-s", SERVICE, "-a", key],
            capture_output=True
        )
        return result.returncode == 0
    except Exception:
        return False


def list_keys() -> list[str]:
    """List all keys stored under the service."""
    try:
        result = subprocess.run(
            ["security", "dump-keychain"],
            capture_output=True,
            text=True
        )
        keys = []
        current_service = None
        for line in result.stdout.split("\n"):
            if f'"svce"<blob>="{SERVICE}"' in line:
                current_service = SERVICE
            elif '"acct"<blob>="' in line and current_service == SERVICE:
                key = line.split('"acct"<blob>="')[1].split('"')[0]
                keys.append(key)
                current_service = None
        return keys
    except Exception:
        return []


def main():
    if len(sys.argv) < 2:
        print("Usage: keychain.py <get|set|delete|list> [key] [value]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "list":
        keys = list_keys()
        if keys:
            print("Stored keys:")
            for key in keys:
                print(f"  - {key}")
        else:
            print("No keys found")
    
    elif action == "get":
        if len(sys.argv) < 3:
            print("Usage: keychain.py get <key>")
            sys.exit(1)
        key = sys.argv[2]
        value = get(key)
        if value:
            print(value)
        else:
            print(f"Key '{key}' not found", file=sys.stderr)
            sys.exit(1)
    
    elif action == "set":
        if len(sys.argv) < 4:
            print("Usage: keychain.py set <key> <value>")
            sys.exit(1)
        key = sys.argv[2]
        value = sys.argv[3]
        if set(key, value):
            print(f"✓ Stored '{key}'")
        else:
            print(f"✗ Failed to store '{key}'", file=sys.stderr)
            sys.exit(1)
    
    elif action == "delete":
        if len(sys.argv) < 3:
            print("Usage: keychain.py delete <key>")
            sys.exit(1)
        key = sys.argv[2]
        if delete(key):
            print(f"✓ Deleted '{key}'")
        else:
            print(f"✗ Failed to delete '{key}'", file=sys.stderr)
            sys.exit(1)
    
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
