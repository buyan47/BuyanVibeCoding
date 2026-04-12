"""
Marriott Receipt Parser
────────────────────────
Extracts structured data from Marriott hotel folio / receipt PDFs and HTML emails.

Fields extracted:
  - date          : check-in date (YYYY-MM-DD)
  - checkout_date : check-out date (YYYY-MM-DD)
  - amount        : total charged (float)
  - description   : property name + city
  - confirmation  : Marriott confirmation number
  - nights        : number of nights (int)
  - vendor        : always "Marriott"
  - source_file   : path of the parsed file
"""

import re
import os
from typing import Dict, Optional

import pdfplumber
from bs4 import BeautifulSoup


class MarriottParser:
    """Parse a single Marriott receipt file (PDF or HTML) into a structured dict."""

    VENDOR = "Marriott"

    def parse(self, file_path: str) -> Dict:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            text = self._read_pdf(file_path)
        elif ext in (".html", ".htm"):
            text = self._read_html(file_path)
        else:
            try:
                text = self._read_pdf(file_path)
            except Exception:
                with open(file_path, "r", errors="replace") as fh:
                    text = fh.read()

        check_in  = self._extract_checkin(text)
        check_out = self._extract_checkout(text)

        return {
            "vendor":        self.VENDOR,
            "date":          check_in,
            "checkout_date": check_out,
            "nights":        self._calc_nights(check_in, check_out),
            "amount":        self._extract_amount(text),
            "description":   self._extract_description(text),
            "confirmation":  self._extract_confirmation(text),
            "source_file":   file_path,
        }

    # ── Readers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _read_pdf(path: str) -> str:
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return "\n".join(pages)

    @staticmethod
    def _read_html(path: str) -> str:
        with open(path, "r", errors="replace") as fh:
            soup = BeautifulSoup(fh.read(), "lxml")
        return soup.get_text(separator="\n")

    # ── Field extractors ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_checkin(text: str) -> Optional[str]:
        """
        Folio PDFs show:  'Check-In  01/20/2024'  or  'Arrival  January 20, 2024'
        Confirmation emails show: 'Check-in: Sunday, January 20, 2024'
        """
        for pattern in (
            r"(?:Check[-\s]?[Ii]n|Arrival|Arrived)\s*[:\-]?\s*(?:\w+,\s+)?(\w+ \d{1,2},?\s+\d{4})",
            r"(?:Check[-\s]?[Ii]n|Arrival)\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4})",
            r"(?:Check[-\s]?[Ii]n|Arrival)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
        ):
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return _normalise_date(m.group(1))
        return None

    @staticmethod
    def _extract_checkout(text: str) -> Optional[str]:
        for pattern in (
            r"(?:Check[-\s]?[Oo]ut|Departure|Departed)\s*[:\-]?\s*(?:\w+,\s+)?(\w+ \d{1,2},?\s+\d{4})",
            r"(?:Check[-\s]?[Oo]ut|Departure)\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4})",
            r"(?:Check[-\s]?[Oo]ut|Departure)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
        ):
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return _normalise_date(m.group(1))
        return None

    @staticmethod
    def _extract_amount(text: str) -> Optional[float]:
        """
        Look for 'Total Amount Due  $456.78' or 'Balance Due  456.78'.
        Marriott folios often list room charges per night; we want the grand total.
        """
        for label in (
            r"(?:Total\s+)?Amount\s+(?:Due|Charged|Paid)",
            r"Grand\s+Total",
            r"Total\s+Charges",
            r"Balance\s+Due",
            r"Total",
        ):
            m = re.search(label + r"\s*\$?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
            if m:
                return float(m.group(1).replace(",", ""))

        # Fall back: last dollar figure
        amounts = re.findall(r"\$\s*([\d,]+\.\d{2})", text)
        if amounts:
            return float(amounts[-1].replace(",", ""))
        return None

    @staticmethod
    def _extract_description(text: str) -> Optional[str]:
        """
        Try to get the property name (e.g. 'New York Marriott Marquis') and city.
        Folios usually have the hotel name at the top.
        """
        # Pattern: line containing "Marriott" that is not a legal/header boilerplate
        lines = text.splitlines()
        for line in lines[:30]:             # hotel name is almost always near the top
            line = line.strip()
            if re.search(r"Marriott|Courtyard|Sheraton|Westin|W Hotel|Renaissance", line, re.IGNORECASE):
                if len(line) > 5 and not re.search(r"copyright|reserved|bonvoy", line, re.IGNORECASE):
                    return line

        # Fallback: "Property: ..."
        m = re.search(r"(?:Property|Hotel|Resort)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

        return "Marriott Stay"

    @staticmethod
    def _extract_confirmation(text: str) -> Optional[str]:
        m = re.search(
            r"(?:Confirmation|Reservation|Booking)\s*(?:#|No\.?|Number)?\s*[:\-]?\s*([A-Z0-9]{6,12})",
            text, re.IGNORECASE
        )
        return m.group(1).strip() if m else None

    @staticmethod
    def _calc_nights(check_in: Optional[str], check_out: Optional[str]) -> Optional[int]:
        if not check_in or not check_out:
            return None
        from dateutil import parser as dparser
        try:
            return (dparser.parse(check_out) - dparser.parse(check_in)).days
        except Exception:
            return None


# ── Date helpers ──────────────────────────────────────────────────────────────

def _normalise_date(s: str) -> Optional[str]:
    from dateutil import parser as dparser
    try:
        return dparser.parse(s).strftime("%Y-%m-%d")
    except Exception:
        return s.strip()
