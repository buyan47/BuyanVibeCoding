"""
Travel Receipt Automation — Main Orchestrator
═══════════════════════════════════════════════
Runs all three tasks end-to-end:

  Task 1 — Scan Gmail by month range → download attachments → upload to Google Drive
  Task 2 — Parse Amtrak receipts     → add rows to Excel/CSV
  Task 3 — Parse Marriott receipts   → add rows to Excel/CSV

Usage:
  python main.py --start 2024-01 --end 2024-03

Optional flags:
  --vendors amtrak marriott uber   (default: all three)
  --skip-drive                     skip the Drive upload step
  --download-dir  downloads/       local folder for raw attachments
  --output-dir    output/          local folder for Excel/CSV output
  --parse-only    <dir>            skip Gmail; parse files already in <dir>
"""

import argparse
import os
import sys

from auth          import get_credentials
from gmail_scanner import GmailScanner
from drive_uploader import DriveUploader
from parsers        import AmtrakParser, MarriottParser, UberParser
from excel_writer   import write_receipts
from config         import OUTPUT_DIR


PARSERS = {
    "amtrak":   AmtrakParser(),
    "marriott": MarriottParser(),
    "uber":     UberParser(),
}


def main():
    args = _parse_args()

    print("=" * 60)
    print("  Travel Receipt Automation")
    print("=" * 60)

    # ── Authenticate ─────────────────────────────────────────────────────────
    print("\n[Auth] Authenticating with Google …")
    creds = get_credentials()
    print("[Auth] OK")

    downloaded_records = []

    # ── Task 1: Gmail scan + Drive upload ────────────────────────────────────
    if not args.parse_only:
        print(f"\n{'─'*60}")
        print(f"  TASK 1 — Gmail scan  ({args.start} → {args.end})")
        print(f"{'─'*60}")

        scanner = GmailScanner(creds)
        downloaded_records = scanner.download_receipts(
            start_month  = args.start,
            end_month    = args.end,
            download_dir = args.download_dir,
            vendors      = args.vendors,
        )
        print(f"\n[Task 1] Downloaded {len(downloaded_records)} file(s).")

        if not args.skip_drive and downloaded_records:
            print(f"\n[Task 1] Uploading to Google Drive folder …")
            uploader = DriveUploader(creds)
            uploader.upload_many(downloaded_records)
            print(f"[Task 1] Drive upload complete.")
    else:
        # --parse-only: load files from a local directory instead of Gmail
        downloaded_records = _load_local_files(args.parse_only, args.vendors)
        print(f"\n[parse-only] Found {len(downloaded_records)} local file(s).")

    # ── Tasks 2 & 3: Parse receipts ──────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  TASKS 2 & 3 — Parsing receipts")
    print(f"{'─'*60}")

    parsed_records = _parse_receipts(downloaded_records)
    print(f"\n[Parse] Successfully parsed {len(parsed_records)} receipt(s).")

    if not parsed_records:
        print("\n[Warn] No records to write. Exiting.")
        sys.exit(0)

    # ── Write Excel + CSV ────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  Writing output files")
    print(f"{'─'*60}")

    paths = write_receipts(parsed_records, output_dir=args.output_dir)

    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"  Excel : {paths['excel']}")
    print(f"  CSV   : {paths['csv']}")
    print(f"{'='*60}\n")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_receipts(records: list) -> list:
    """Run vendor-specific parsers and return structured dicts."""
    results = []
    for rec in records:
        vendor     = rec.get("vendor", "").lower()
        local_path = rec.get("local_path", "")

        parser = PARSERS.get(vendor)
        if not parser:
            print(f"  [Skip] No parser for vendor='{vendor}'  ({os.path.basename(local_path)})")
            continue
        if not local_path or not os.path.exists(local_path):
            print(f"  [Skip] File not found: {local_path}")
            continue

        try:
            parsed = parser.parse(local_path)
            print(f"  [Parsed] {vendor.capitalize():10s}  {parsed.get('date','?'):12s}  ${parsed.get('amount') or 0:>8.2f}  {(parsed.get('description') or '')[:40]}")
            results.append(parsed)
        except Exception as exc:
            print(f"  [Error] Could not parse {local_path}: {exc}")

    return results


def _load_local_files(directory: str, vendors: list) -> list:
    """
    Build file-record dicts from files already in *directory*.
    Vendor is inferred from the filename prefix (set by GmailScanner).
    """
    records = []
    for fname in sorted(os.listdir(directory)):
        fpath  = os.path.join(directory, fname)
        vendor = _infer_vendor(fname)
        if vendors and vendor not in vendors:
            continue
        records.append({
            "vendor":     vendor,
            "local_path": fpath,
            "filename":   fname,
            "subject":    fname,
            "date":       None,
        })
    return records


def _infer_vendor(filename: str) -> str:
    fname = filename.lower()
    for v in ("amtrak", "marriott", "uber"):
        if v in fname:
            return v
    return "unknown"


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Download travel receipts from Gmail and export to Excel/CSV."
    )
    parser.add_argument("--start",       default="2024-01",    help="Start month YYYY-MM")
    parser.add_argument("--end",         default="2024-12",    help="End month   YYYY-MM")
    parser.add_argument("--vendors",     nargs="+", default=["amtrak", "marriott", "uber"],
                        help="Vendors to process (amtrak marriott uber)")
    parser.add_argument("--skip-drive",  action="store_true",  help="Skip Google Drive upload")
    parser.add_argument("--download-dir",default="downloads",  help="Local dir for raw files")
    parser.add_argument("--output-dir",  default=OUTPUT_DIR,   help="Local dir for output files")
    parser.add_argument("--parse-only",  metavar="DIR",        help="Skip Gmail; parse files in DIR")
    return parser.parse_args()


if __name__ == "__main__":
    main()
