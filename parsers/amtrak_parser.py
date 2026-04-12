"""
Amtrak Receipt Parser
──────────────────────
Parses Amtrak HTML sales-receipt emails (from etickets@amtrak.com).

Real email structure observed:
  Subject : SALES RECEIPT
  From    : etickets@amtrak.com
  Body contains (plain-text after HTML stripping):
    "Reservation Number - D92DC4"
    "Wilmington, DE to Washington, DC - Union Station (Round-Trip)"
    "APRIL 7, 2026"                        ← purchase date
    "Purchase Summary - Ticket Number 0970632534586"
    "TRAIN 151: Wilmington, DE to Washington, DC - Union Station (Round-Trip)"
    "Depart 5:24 AM, Wednesday, April 15, 2026"
    "Total Charged by Amtrak  $212.00"
    Passengers section: "Buyan Thyagarajan"

Fields extracted:
  date           – first departure date  (YYYY-MM-DD)
  purchase_date  – date email was sent / ticket purchased (YYYY-MM-DD)
  amount         – Total Charged by Amtrak (float)
  description    – route string, e.g. "Wilmington, DE → Washington, DC - Union Station"
  reservation    – reservation / confirmation number  (e.g. D92DC4)
  ticket_number  – ticket number (e.g. 0970632534586)
  passenger      – passenger name (e.g. Buyan Thyagarajan)
  vendor         – always "Amtrak"
  source_file    – path of the parsed file
"""

import re
import os
from typing import Dict, Optional, List

from bs4 import BeautifulSoup


class AmtrakParser:
    VENDOR = "Amtrak"

    def parse(self, file_path: str) -> Dict:
        text = self._read(file_path)
        return {
            "vendor":        self.VENDOR,
            "date":          self._extract_departure_date(text),
            "purchase_date": self._extract_purchase_date(text),
            "amount":        self._extract_amount(text),
            "description":   self._extract_description(text),
            "reservation":   self._extract_reservation(text),
            "ticket_number": self._extract_ticket_number(text),
            "passenger":     self._extract_passenger(text),
            "source_file":   file_path,
        }

    # ── Reader ────────────────────────────────────────────────────────────────

    @staticmethod
    def _read(path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".html", ".htm", ".txt"):
            with open(path, "r", errors="replace") as fh:
                raw = fh.read()
            if ext in (".html", ".htm") or raw.lstrip().startswith("<"):
                return BeautifulSoup(raw, "lxml").get_text(separator="\n")
            return raw
        # Try PDF via pdfplumber
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")
            return "\n".join(pages)
        except Exception:
            with open(path, "r", errors="replace") as fh:
                return fh.read()

    # ── Field extractors ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_departure_date(text: str) -> Optional[str]:
        """
        Find 'Depart HH:MM AM/PM, DayOfWeek, Month DD, YYYY'
        e.g. 'Depart 5:24 AM, Wednesday, April 15, 2026'
        Return the FIRST (earliest) departure date found.
        """
        matches = re.findall(
            r"Depart\s+\d{1,2}:\d{2}\s+[AP]M,\s+\w+,\s+(\w+ \d{1,2},\s*\d{4})",
            text, re.IGNORECASE
        )
        if matches:
            return _parse_date(matches[0])

        # Fallback: look for standalone date near "APRIL 7, 2026" style
        m = re.search(r"\b(January|February|March|April|May|June|July|August|"
                      r"September|October|November|December)\s+\d{1,2},\s*\d{4}\b",
                      text, re.IGNORECASE)
        if m:
            return _parse_date(m.group(0))
        return None

    @staticmethod
    def _extract_purchase_date(text: str) -> Optional[str]:
        """
        'Purchased: 04/07/2026 7:33 AM PT'
        """
        m = re.search(r"Purchased[:\s]+(\d{1,2}/\d{1,2}/\d{4})", text, re.IGNORECASE)
        if m:
            return _parse_date(m.group(1))
        return None

    @staticmethod
    def _extract_amount(text: str) -> Optional[float]:
        """
        'Total Charged by Amtrak  $212.00'
        """
        m = re.search(r"Total\s+Charged\s+by\s+Amtrak\s*\$?\s*([\d,]+\.\d{2})",
                      text, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))

        # Fallback: 'Total  $212.00'
        m = re.search(r"\bTotal\b\s*\$?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))

        # Last resort: last $ amount
        amounts = re.findall(r"\$\s*([\d,]+\.\d{2})", text)
        if amounts:
            return float(amounts[-1].replace(",", ""))
        return None

    @staticmethod
    def _extract_description(text: str) -> Optional[str]:
        """
        'Wilmington, DE to Washington, DC - Union Station (Round-Trip)'
        This appears right after the Reservation Number line.
        """
        # Pattern: "City, ST to City, ST ..." on its own line
        m = re.search(
            r"([A-Za-z ,\-]+,\s*[A-Z]{2}\s+to\s+[A-Za-z ,\-]+(?:Station|Terminal|Airport)?[^\n]*)",
            text, re.IGNORECASE
        )
        if m:
            desc = m.group(1).strip().rstrip(".")
            # Normalise "X to Y" → "X → Y"
            desc = re.sub(r"\s+to\s+", " → ", desc, count=1, flags=re.IGNORECASE)
            return desc

        # Fallback: TRAIN line
        m = re.search(r"TRAIN\s+\d+[:\s]+(.+)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return "Amtrak Trip"

    @staticmethod
    def _extract_reservation(text: str) -> Optional[str]:
        """
        'Reservation Number - D92DC4'
        """
        m = re.search(
            r"Reservation\s+Number\s*[-–:]\s*([A-Z0-9]{4,12})",
            text, re.IGNORECASE
        )
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_ticket_number(text: str) -> Optional[str]:
        """
        'Purchase Summary - Ticket Number 0970632534586'
        """
        m = re.search(
            r"Ticket\s+Number\s*[-–:]?\s*(\d{6,20})",
            text, re.IGNORECASE
        )
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_passenger(text: str) -> Optional[str]:
        """
        The 'Passengers' section contains a box with the name.
        Look for a proper-cased name (First Last) following the 'Passengers' header.
        """
        m = re.search(
            r"Passengers?\s*\n+\s*([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text
        )
        if m:
            return m.group(1).strip()

        # Fallback: any proper-cased two-word name after "Passenger"
        m = re.search(
            r"Passenger[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)",
            text
        )
        return m.group(1).strip() if m else None


# ── Date helper ───────────────────────────────────────────────────────────────

def _parse_date(s: str) -> Optional[str]:
    from dateutil import parser as dparser
    try:
        return dparser.parse(s).strftime("%Y-%m-%d")
    except Exception:
        return s.strip()
