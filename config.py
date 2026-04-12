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
# Queries use actual sender addresses confirmed from real receipts.
# Amtrak  : etickets@amtrak.com  – subject "SALES RECEIPT"
# Marriott: PDF attachment emails from Marriott (folio / confirmation)
# Uber    : noreply@uber.com     – subject contains "trip" or "tipping"
GMAIL_QUERIES = {
    "amtrak":   'from:etickets@amtrak.com subject:"SALES RECEIPT"',
    "marriott": '(from:marriott.com OR from:email.marriott.com) (subject:"receipt" OR subject:"folio" OR subject:"stay" OR subject:"confirmation")',
    "uber":     'from:noreply@uber.com (subject:"trip" OR subject:"tipping" OR subject:"receipt")',
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
