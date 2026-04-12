"""
Two-step Google OAuth setup for headless environments.

STEP 1 — get the auth URL:
    python3 setup_auth.py

STEP 2 — paste the code Google gave you:
    python3 setup_auth.py --code "4/0AX4XfWh..."
"""

import sys
import argparse
from google_auth_oauthlib.flow import InstalledAppFlow
from config import CREDENTIALS_FILE, TOKEN_FILE, SCOPES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", help="Authorization code from Google")
    args = parser.parse_args()

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    if not args.code:
        # ── STEP 1: print the auth URL ────────────────────────────────────
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
        )
        print("\n" + "=" * 70)
        print("  STEP 1 of 2 — Open this URL in your browser:")
        print("=" * 70)
        print("\n" + auth_url + "\n")
        print("=" * 70)
        print("  After you click Allow, Google will show you a short code.")
        print("  Copy that code, then run:")
        print()
        print('  python3 setup_auth.py --code "PASTE_CODE_HERE"')
        print("=" * 70 + "\n")
    else:
        # ── STEP 2: exchange code for token ───────────────────────────────
        flow.fetch_token(code=args.code)
        creds = flow.credentials
        with open(TOKEN_FILE, "w") as fh:
            fh.write(creds.to_json())
        print(f"\n[OK] token.json saved. You are now authenticated!")
        print(f"[OK] Run the main script:\n")
        print(f"     python3 main.py --start 2026-01 --end 2026-04\n")


if __name__ == "__main__":
    main()
