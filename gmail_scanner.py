"""
Gmail Scanner
─────────────
Searches Gmail for travel receipts within a given month range and downloads
every attachment (PDF / HTML) to a local directory.

Usage (from main.py or interactively):
    from gmail_scanner import GmailScanner
    scanner = GmailScanner(creds)
    files = scanner.download_receipts("2024-01", "2024-03", download_dir="downloads")
"""

import base64
import os
from datetime import datetime, date
from typing import List, Dict, Optional

import httplib2
import google_auth_httplib2
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from config import GMAIL_QUERIES


def _build_http(creds: Credentials):
    """Build an authorized HTTP client (SSL verification relaxed for proxy environments)."""
    http = httplib2.Http(disable_ssl_certificate_validation=True)
    return google_auth_httplib2.AuthorizedHttp(creds, http=http)


class GmailScanner:
    """Downloads travel-receipt attachments from Gmail for a given date range."""

    # MIME types we want to save
    ATTACHMENT_MIME_WHITELIST = {
        "application/pdf",
        "text/html",
        "text/plain",
    }

    def __init__(self, creds: Credentials):
        self.service = build("gmail", "v1", http=_build_http(creds))

    # ── Public API ────────────────────────────────────────────────────────────

    def download_receipts(
        self,
        start_month: str,          # "YYYY-MM"
        end_month: str,            # "YYYY-MM"  (inclusive)
        download_dir: str = "downloads",
        vendors: Optional[List[str]] = None,  # subset of GMAIL_QUERIES keys
    ) -> List[Dict]:
        """
        Search Gmail and save attachments.

        Returns a list of dicts:
          {vendor, message_id, subject, date, filename, local_path, mime_type}
        """
        os.makedirs(download_dir, exist_ok=True)

        after_date  = _first_day_of_month(start_month)
        before_date = _last_day_of_month(end_month)
        date_filter = f"after:{after_date.strftime('%Y/%m/%d')} before:{before_date.strftime('%Y/%m/%d')}"

        target_vendors = vendors or list(GMAIL_QUERIES.keys())
        downloaded: List[Dict] = []

        for vendor in target_vendors:
            base_query = GMAIL_QUERIES.get(vendor)
            if not base_query:
                print(f"[WARN] No query configured for vendor '{vendor}', skipping.")
                continue

            full_query = f"{base_query} {date_filter}"
            print(f"\n[Gmail] Searching for {vendor.upper()} receipts …")
            print(f"        Query: {full_query}")

            messages = self._search_messages(full_query)
            print(f"        Found {len(messages)} message(s).")

            for msg_stub in messages:
                msg_id  = msg_stub["id"]
                records = self._process_message(msg_id, vendor, download_dir)
                downloaded.extend(records)

        return downloaded

    # ── Private helpers ───────────────────────────────────────────────────────

    def _search_messages(self, query: str) -> List[Dict]:
        """Return all message stubs matching *query* (handles pagination)."""
        results = []
        page_token = None

        while True:
            kwargs = {"userId": "me", "q": query, "maxResults": 100}
            if page_token:
                kwargs["pageToken"] = page_token

            resp = self.service.users().messages().list(**kwargs).execute()
            results.extend(resp.get("messages", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return results

    def _process_message(
        self, msg_id: str, vendor: str, download_dir: str
    ) -> List[Dict]:
        """
        Fetch a single message, extract metadata, and save any attachments.
        Returns one record per downloaded file.
        """
        msg = (
            self.service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )

        headers  = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        subject  = headers.get("Subject", "(no subject)")
        date_str = headers.get("Date", "")
        msg_date = _parse_email_date(date_str)

        print(f"  → [{vendor}] {msg_date}  {subject[:60]}")

        records = []
        self._extract_parts(
            msg["payload"], msg_id, vendor, subject, msg_date,
            download_dir, records
        )

        # If the message has NO attachments at all, save the HTML/text body
        if not records:
            body_record = self._save_body(
                msg["payload"], msg_id, vendor, subject, msg_date, download_dir
            )
            if body_record:
                records.append(body_record)

        return records

    def _extract_parts(
        self, payload, msg_id, vendor, subject, msg_date, download_dir, records
    ):
        """Recursively walk MIME parts and save attachments."""
        mime = payload.get("mimeType", "")
        body = payload.get("body", {})

        # Inline base64 data (small attachments or body)
        if body.get("data") and mime in self.ATTACHMENT_MIME_WHITELIST:
            filename = payload.get("filename")
            if filename:
                local_path = self._save_data(
                    base64.urlsafe_b64decode(body["data"]),
                    filename, msg_id, vendor, download_dir
                )
                records.append({
                    "vendor": vendor, "message_id": msg_id,
                    "subject": subject, "date": msg_date,
                    "filename": filename, "local_path": local_path,
                    "mime_type": mime,
                })

        # Separate attachment referenced by attachmentId
        if body.get("attachmentId") and mime in self.ATTACHMENT_MIME_WHITELIST:
            filename = payload.get("filename") or f"{msg_id}.pdf"
            att = (
                self.service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=msg_id, id=body["attachmentId"])
                .execute()
            )
            raw_data = base64.urlsafe_b64decode(att["data"])
            local_path = self._save_data(raw_data, filename, msg_id, vendor, download_dir)
            records.append({
                "vendor": vendor, "message_id": msg_id,
                "subject": subject, "date": msg_date,
                "filename": filename, "local_path": local_path,
                "mime_type": mime,
            })

        # Recurse into sub-parts
        for part in payload.get("parts", []):
            self._extract_parts(
                part, msg_id, vendor, subject, msg_date, download_dir, records
            )

    def _save_body(
        self, payload, msg_id, vendor, subject, msg_date, download_dir
    ) -> Optional[Dict]:
        """Save the plain-text or HTML body when there are no attachments."""
        for mime_pref in ("text/html", "text/plain"):
            data = _find_body_data(payload, mime_pref)
            if data:
                ext      = "html" if mime_pref == "text/html" else "txt"
                filename = f"{vendor}_{msg_id}.{ext}"
                local_path = self._save_data(
                    base64.urlsafe_b64decode(data),
                    filename, msg_id, vendor, download_dir
                )
                return {
                    "vendor": vendor, "message_id": msg_id,
                    "subject": subject, "date": msg_date,
                    "filename": filename, "local_path": local_path,
                    "mime_type": mime_pref,
                }
        return None

    @staticmethod
    def _save_data(data: bytes, filename: str, msg_id: str, vendor: str, directory: str) -> str:
        """Write bytes to disk; prefix with vendor+msg_id to avoid collisions."""
        safe_name  = filename.replace("/", "_").replace("\\", "_")
        final_name = f"{vendor}_{msg_id}_{safe_name}"
        local_path = os.path.join(directory, final_name)
        with open(local_path, "wb") as fh:
            fh.write(data)
        print(f"     Saved: {local_path}")
        return local_path


# ── Utility functions ─────────────────────────────────────────────────────────

def _first_day_of_month(ym: str) -> date:
    return datetime.strptime(ym, "%Y-%m").date().replace(day=1)


def _last_day_of_month(ym: str) -> date:
    import calendar
    d = datetime.strptime(ym, "%Y-%m").date()
    last = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=last)


def _parse_email_date(date_str: str) -> str:
    """Return YYYY-MM-DD, or the raw string if parsing fails."""
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str).strftime("%Y-%m-%d")
    except Exception:
        return date_str


def _find_body_data(payload, target_mime: str) -> Optional[str]:
    """Recursively find the first MIME part matching *target_mime*."""
    if payload.get("mimeType") == target_mime:
        return payload.get("body", {}).get("data")
    for part in payload.get("parts", []):
        found = _find_body_data(part, target_mime)
        if found:
            return found
    return None
