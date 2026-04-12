"""
Marriott Receipt Parser
────────────────────────
Parses Marriott hotel folio PDFs (Le Meridien, Courtyard, Sheraton, Westin, etc.)

Real folio structure observed (Le Meridien Madison, Washington DC):
  Top-left  : Property name + address  (e.g. "Le Meridien Madison")
  Right block:
      Page Number      1
      Guest Number     337400
      Folio ID         A
      Arrive Date      17-FEB-26    08:00   ← DD-MMM-YY format
      Depart Date      19-FEB-26    08:32
      No. Of Guest     1
      Room Number      911
      Marriott Bonvoy Number  2950
  Charge table columns: Date | Reference | Description | Charges (USD) | Credits (USD)
  Totals:
      ** Total     460.78    -460.78
      *** Balance    0.00

Fields extracted:
  date           – check-in date  (YYYY-MM-DD)
  checkout_date  – check-out date (YYYY-MM-DD)
  nights         – number of nights (int)
  amount         – total folio charges in USD (float)
  description    – property name  (e.g. "Le Meridien Madison")
  guest_number   – Marriott guest/folio number (e.g. 337400)
  room_number    – room number
  bonvoy_number  – Marriott Bonvoy loyalty number
  guest_name     – guest name from top-left address block
  charge_summary – list of unique charge descriptions
  vendor         – always "Marriott"
  source_file    – path of the parsed file
"""

import re
import os
from typing import Dict, List, Optional

import pdfplumber
from bs4 import BeautifulSoup


class MarriottParser:
    VENDOR = "Marriott"

    def parse(self, file_path: str) -> Dict:
        text = self._read(file_path)

        check_in  = self._extract_arrive_date(text)
        check_out = self._extract_depart_date(text)

        return {
            "vendor":         self.VENDOR,
            "date":           check_in,
            "checkout_date":  check_out,
            "nights":         _calc_nights(check_in, check_out),
            "amount":         self._extract_total(text),
            "description":    self._extract_property_name(text),
            "guest_number":   self._extract_guest_number(text),
            "room_number":    self._extract_room_number(text),
            "bonvoy_number":  self._extract_bonvoy(text),
            "guest_name":     self._extract_guest_name(text),
            "charge_summary": self._extract_charge_summary(text),
            "source_file":    file_path,
        }

    # ── Reader ────────────────────────────────────────────────────────────────

    @staticmethod
    def _read(path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".html", ".htm"):
            with open(path, "r", errors="replace") as fh:
                return BeautifulSoup(fh.read(), "lxml").get_text(separator="\n")
        # Default: PDF via pdfplumber
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return "\n".join(pages)

    # ── Field extractors ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_property_name(text: str) -> str:
        """
        The hotel name is the very first non-blank line of the PDF.
        e.g. 'Le Meridien Madison'
        Also catches Courtyard, Sheraton, Westin, W Hotel, Renaissance variants.
        """
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Accept any line that looks like a property name (not an address/number)
            if re.search(
                r"(Marriott|Meridien|Courtyard|Sheraton|Westin|W Hotel|"
                r"Renaissance|Autograph|Delta|AC Hotel|Moxy|Aloft|Element|"
                r"Four Points|SpringHill|Fairfield|TownePlace|Residence Inn)",
                line, re.IGNORECASE
            ):
                return line
            # Also accept the first short non-address line as the property name
            if len(line) < 60 and not re.search(r"\d{4,}|Tel:|Tax|Page", line):
                return line
        return "Marriott Property"

    @staticmethod
    def _extract_arrive_date(text: str) -> Optional[str]:
        """
        'Arrive Date      17-FEB-26    08:00'
        Date format: DD-MMM-YY  (two-digit year, always 20xx for our purposes)
        """
        m = re.search(
            r"Arrive\s+Date\s+(\d{1,2}-[A-Z]{3}-\d{2,4})",
            text, re.IGNORECASE
        )
        if m:
            return _parse_marriott_date(m.group(1))

        # Fallback: generic check-in patterns
        m = re.search(
            r"(?:Check[-\s]?[Ii]n|Arrival)\s*[:\-]?\s*(\d{1,2}-[A-Z]{3}-\d{2,4}|\d{1,2}/\d{1,2}/\d{2,4})",
            text, re.IGNORECASE
        )
        return _parse_marriott_date(m.group(1)) if m else None

    @staticmethod
    def _extract_depart_date(text: str) -> Optional[str]:
        """
        'Depart Date      19-FEB-26    08:32'
        """
        m = re.search(
            r"Depart\s+Date\s+(\d{1,2}-[A-Z]{3}-\d{2,4})",
            text, re.IGNORECASE
        )
        if m:
            return _parse_marriott_date(m.group(1))

        m = re.search(
            r"(?:Check[-\s]?[Oo]ut|Departure)\s*[:\-]?\s*(\d{1,2}-[A-Z]{3}-\d{2,4}|\d{1,2}/\d{1,2}/\d{2,4})",
            text, re.IGNORECASE
        )
        return _parse_marriott_date(m.group(1)) if m else None

    @staticmethod
    def _extract_total(text: str) -> Optional[float]:
        """
        '** Total     460.78    -460.78'
        The first number after '** Total' is total charges; we want that.
        Also handles '*** Balance   0.00' — we want Total, not Balance.
        """
        # '** Total  460.78' or '** Total  460.78  -460.78'
        m = re.search(
            r"\*+\s*Total\s+([\d,]+\.\d{2})",
            text, re.IGNORECASE
        )
        if m:
            return float(m.group(1).replace(",", ""))

        # Fallback labels
        for label in ("Total Amount Due", "Grand Total", "Amount Due", "Total Charges"):
            m = re.search(label + r"\s*\$?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
            if m:
                return float(m.group(1).replace(",", ""))

        # Last positive dollar amount
        amounts = re.findall(r"(?<!\-)\b([\d,]+\.\d{2})\b", text)
        if amounts:
            return float(amounts[-1].replace(",", ""))
        return None

    @staticmethod
    def _extract_guest_number(text: str) -> Optional[str]:
        """'Guest Number     337400'"""
        m = re.search(r"Guest\s+Number\s+(\d+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_room_number(text: str) -> Optional[str]:
        """'Room Number      911'"""
        m = re.search(r"Room\s+Number\s+(\w+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_bonvoy(text: str) -> Optional[str]:
        """'Marriott Bonvoy Number  2950'"""
        m = re.search(r"(?:Marriott\s+)?Bonvoy\s+Number\s+(\w+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_guest_name(text: str) -> Optional[str]:
        """
        Guest name is in the top-left address block — all caps, before the street address.
        e.g. 'BUYAN THYAGARAJAN'
        """
        m = re.search(r"^([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?)\s*$", text, re.MULTILINE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_charge_summary(text: str) -> str:
        """
        Extract unique charge description labels from the folio table.
        e.g. 'Room Chrg - Govt./Military | Occupancy Tax | Bistro Food'
        """
        descriptions = re.findall(
            r"(?:\d{1,2}-[A-Z]{3}-\d{2,4})\s+\w+\s+(.+?)\s+[\d,]+\.\d{2}",
            text
        )
        seen   = []
        unique = []
        for d in descriptions:
            d = d.strip()
            if d and d not in seen:
                seen.append(d)
                unique.append(d)
        return " | ".join(unique) if unique else "Hotel Stay"


# ── Date helpers ──────────────────────────────────────────────────────────────

def _parse_marriott_date(s: str) -> Optional[str]:
    """
    Handle Marriott's DD-MMM-YY format (e.g. '17-FEB-26' → '2026-02-17').
    dateutil parses two-digit years with century pivot at 50:
      00-49 → 2000-2049, 50-99 → 1950-1999.
    Since all travel is 2020+, this is fine.
    """
    from dateutil import parser as dparser
    try:
        return dparser.parse(s).strftime("%Y-%m-%d")
    except Exception:
        return s.strip()


def _calc_nights(check_in: Optional[str], check_out: Optional[str]) -> Optional[int]:
    if not check_in or not check_out:
        return None
    from dateutil import parser as dparser
    try:
        return (dparser.parse(check_out) - dparser.parse(check_in)).days
    except Exception:
        return None
