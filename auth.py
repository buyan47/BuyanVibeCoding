"""
Google OAuth2 authentication helper.
Handles the browser-based first-login flow and caches the token locally.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import CREDENTIALS_FILE, TOKEN_FILE, SCOPES


def get_credentials() -> Credentials:
    """
    Return valid Google credentials, refreshing or re-authorising as needed.

    First run: opens a browser window for the user to grant access.
    Subsequent runs: loads the cached token from TOKEN_FILE.
    """
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_FILE}' not found.\n"
                    "Download it from Google Cloud Console:\n"
                    "  APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON\n"
                    f"Then rename the file to '{CREDENTIALS_FILE}' and place it in this directory."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as fh:
            fh.write(creds.to_json())

    return creds
