"""
Central configuration for Travel Receipt Automation.
Edit the values below to match your setup.
"""

# ── Google OAuth credentials file (download from Google Cloud Console) ──────
CREDENTIALS_FILE = "credentials.json"   # OAuth 2.0 client secrets
TOKEN_FILE       = "token.json"         # auto-created after first login

# ── Google Drive ─────────────────────────────────────────────────────────────
DRIVE_FOLDER_NAME = "Travel Receipts"   # top-level folder in My Drive

# ── Gmail search ─────────────────────────────────────────────────────────────
# These queries are passed directly to the Gmail search API.
# You can tighten them (e.g. add  from:receipts@amtrak.com) after testing.
GMAIL_QUERIES = {
    "amtrak":   'subject:"Amtrak" (subject:"receipt" OR subject:"eticket" OR subject:"booking")',
    "marriott": 'subject:"Marriott" (subject:"receipt" OR subject:"folio" OR subject:"confirmation")',
    "uber":     'from:uber.com (subject:"receipt" OR subject:"Your trip")',
}

# ── Output files ─────────────────────────────────────────────────────────────
OUTPUT_DIR      = "output"          # local directory for generated files
EXCEL_FILENAME  = "travel_receipts.xlsx"
CSV_FILENAME    = "travel_receipts.csv"

# ── OAuth scopes needed ───────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive",
]
