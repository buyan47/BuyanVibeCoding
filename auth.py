"""
Google OAuth2 authentication helper.
Handles both local (browser) and server/headless (console) environments.
"""

import os
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import CREDENTIALS_FILE, TOKEN_FILE, SCOPES


def get_credentials() -> Credentials:
    """
    Return valid Google credentials, refreshing or re-authorising as needed.

    - If token.json exists and is valid: uses it silently.
    - If expired but has refresh token: refreshes silently.
    - First run (no token): prints an auth URL → you visit it in any browser →
      paste the code back → token.json is saved for future runs.
    """
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[Auth] Refreshing expired token …")
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print("\n" + "="*60)
                print("  credentials.json not found!")
                print("="*60)
                print("""
Follow these steps to create it:

1. Go to https://console.cloud.google.com/
2. Create a new project (e.g. 'TravelReceipts')
3. Enable APIs:
     APIs & Services → Library → search 'Gmail API' → Enable
     APIs & Services → Library → search 'Drive API' → Enable
4. Create credentials:
     APIs & Services → Credentials
     → Create Credentials → OAuth 2.0 Client ID
     → Application type: Desktop app
     → Name: TravelReceipts → Create
5. Download JSON → rename to 'credentials.json'
6. Place it here:  """ + os.path.abspath(CREDENTIALS_FILE) + """

Then re-run:  python3 main.py --start YYYY-MM --end YYYY-MM
""")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)

            # Try local server first; fall back to manual copy-paste flow
            try:
                creds = flow.run_local_server(port=0, open_browser=True)
            except Exception:
                creds = _run_console_flow(flow)

        with open(TOKEN_FILE, "w") as fh:
            fh.write(creds.to_json())
        print("[Auth] token.json saved — future runs will skip this step.")

    return creds


def _run_console_flow(flow):
    """
    Manual OAuth flow for headless / server environments.
    Prints the auth URL → user visits it in their browser → pastes the code back.
    """
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )

    print("\n" + "=" * 60)
    print("  Google Authorization Required")
    print("=" * 60)
    print("\n1. Open this URL in your browser:\n")
    print("   " + auth_url)
    print("\n2. Sign in and click Allow")
    print("3. Copy the authorization code shown on the page")
    print("4. Paste it below and press Enter\n")

    code = input("Authorization code: ").strip()
    flow.fetch_token(code=code)
    return flow.credentials
