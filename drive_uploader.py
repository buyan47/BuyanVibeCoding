"""
Google Drive Uploader
──────────────────────
Uploads receipt files into an existing Google Drive folder.

Target structure:
  My Drive > VibeCodingExperiments > TravelReceipts > Amtrak/
                                                     > Marriott/
                                                     > Uber/

The root folder ID is read from config.DRIVE_FOLDER_ID (taken directly
from the Drive URL) so no searching is needed.

Usage:
    from drive_uploader import DriveUploader
    uploader = DriveUploader(creds)
    file_id  = uploader.upload("downloads/amtrak_abc123.pdf", subfolder="Amtrak")
"""

import os
import mimetypes
from typing import Optional

import httplib2
import google_auth_httplib2
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

from config import DRIVE_FOLDER_ID, DRIVE_FOLDER_NAME


def _build_http(creds: Credentials):
    """Build an authorized HTTP client (SSL verification relaxed for proxy environments)."""
    http = httplib2.Http(disable_ssl_certificate_validation=True)
    return google_auth_httplib2.AuthorizedHttp(creds, http=http)


class DriveUploader:
    """Uploads receipt files into VibeCodingExperiments/TravelReceipts on Google Drive."""

    def __init__(self, creds: Credentials):
        self.service         = build("drive", "v3", http=_build_http(creds))
        self._root_id        = DRIVE_FOLDER_ID          # pinned — no search needed
        self._subfolder_cache: dict = {}                # vendor name → folder id
        print(f"  [Drive] Root folder: {DRIVE_FOLDER_NAME}  (id={self._root_id})")

    # ── Public API ────────────────────────────────────────────────────────────

    def upload(self, local_path: str, subfolder: Optional[str] = None) -> str:
        """
        Upload *local_path* to Drive.
        Places the file inside TravelReceipts/<subfolder> (subfolder = vendor name).
        Returns the Drive file ID.
        """
        parent_id = self._get_or_create_subfolder(subfolder) if subfolder else self._root_id

        filename  = os.path.basename(local_path)
        mime_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"

        # Skip if already uploaded
        existing_id = self._find_file(filename, parent_id)
        if existing_id:
            print(f"  [Drive] Already exists, skipping: {filename}")
            return existing_id

        file_metadata = {"name": filename, "parents": [parent_id]}
        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)

        created = (
            self.service.files()
            .create(body=file_metadata, media_body=media, fields="id,name")
            .execute()
        )
        print(f"  [Drive] Uploaded: {created['name']}  (id={created['id']})")
        return created["id"]

    def upload_many(self, file_records: list, subfolder_key: str = "vendor") -> list:
        """
        Upload a list of file-record dicts (as returned by GmailScanner).
        Adds a 'drive_file_id' key to each record.
        """
        for rec in file_records:
            subfolder = rec.get(subfolder_key, "").capitalize()
            rec["drive_file_id"] = self.upload(rec["local_path"], subfolder=subfolder)
        return file_records

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_or_create_subfolder(self, name: str) -> str:
        """Return (creating if needed) the ID of TravelReceipts/<name>."""
        if name not in self._subfolder_cache:
            self._subfolder_cache[name] = self._get_or_create_folder(name, self._root_id)
        return self._subfolder_cache[name]

    def _get_or_create_folder(self, name: str, parent_id: str) -> str:
        existing = self._find_folder(name, parent_id)
        if existing:
            return existing

        folder = (
            self.service.files()
            .create(
                body={
                    "name": name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                },
                fields="id,name",
            )
            .execute()
        )
        print(f"  [Drive] Created subfolder: {folder['name']}  (id={folder['id']})")
        return folder["id"]

    def _find_folder(self, name: str, parent_id: str) -> Optional[str]:
        query = (
            f"name='{name}' "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and '{parent_id}' in parents "
            f"and trashed=false"
        )
        return self._query_first(query)

    def _find_file(self, name: str, parent_id: str) -> Optional[str]:
        query = (
            f"name='{name}' "
            f"and '{parent_id}' in parents "
            f"and trashed=false"
        )
        return self._query_first(query)

    def _query_first(self, query: str) -> Optional[str]:
        resp = (
            self.service.files()
            .list(q=query, spaces="drive", fields="files(id,name)", pageSize=1)
            .execute()
        )
        files = resp.get("files", [])
        return files[0]["id"] if files else None
