"""
Amtrak Receipt Parser
──────────────────────
Extracts structured data from Amtrak e-ticket / receipt PDFs (and HTML fallbacks).

Fields extracted:
  - date          : travel date (YYYY-MM-DD)
  - amount        : total charged (float)
  - description   : route  e.g. "New York → Washington DC"
  - ticket_number : Amtrak confirmation / ticket number
  - passenger     : passenger name if present
  - vendor        : always "Amtrak"
  - source_file   : path of the parsed file
"""

import re
import os
from typing import Dict, Optional

import pdfplumber
from bs4 import BeautifulSoup


class AmtrakParser:
    """Parse a single Amtrak receipt file (PDF or HTML) into a structured dict."""

    VENDOR = "Amtrak"

    def parse(self, file_path: str) -> Dict:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            text = self._read_pdf(file_path)
        elif ext in (".html", ".htm"):
            text = self._read_html(file_path)
        else:
            # Try PDF first, fall back to plain text
            try:
                text = self._read_pdf(file_path)
            except Exception:
                with open(file_path, "r", errors="replace") as fh:
                    text = fh.read()

        return {
            "vendor":        self.VENDOR,
            "date":          self._extract_date(text),
            "amount":        self._extract_amount(text),
            "description":   self._extract_description(text),
            "ticket_number": self._extract_ticket_number(text),
            "passenger":     self._extract_passenger(text),
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
    def _extract_date(text: str) -> Optional[str]:
        """
        Amtrak PDFs usually show the travel date as:
          'Departs  Mon, Jan 15, 2024'  or  '01/15/2024'
        """
        # Pattern 1: "Mon, Jan 15, 2024" or "January 15, 2024"
        m = re.search(
            r"(?:Departs?|Travel Date|Date)[:\s]+(?:\w+,\s+)?(\w+ \d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if m:
            return _parse_loose_date(m.group(1))

        # Pattern 2: MM/DD/YYYY or YYYY-MM-DD
        m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b", text)
        if m:
            return _normalise_date(m.group(1))

        return None

    @staticmethod
    def _extract_amount(text: str) -> Optional[float]:
        """
        Look for 'Total  $123.45' or 'Amount Charged  $123.45'.
        Returns the LAST (largest / final) dollar amount found after a total label.
        """
        # Prefer explicit total labels
        for label in (
            r"Total(?:\s+Charged)?",
            r"Amount(?:\s+Due|\s+Charged)?",
            r"Grand Total",
        ):
            m = re.search(label + r"\s*\$?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
            if m:
                return float(m.group(1).replace(",", ""))

        # Fall back: last dollar amount in the document
        amounts = re.findall(r"\$\s*([\d,]+\.\d{2})", text)
        if amounts:
            return float(amounts[-1].replace(",", ""))

        return None

    @staticmethod
    def _extract_description(text: str) -> Optional[str]:
        """
        Build a route string like 'New York Penn Station → Washington Union Station'.
        Amtrak PDFs typically have 'From  New York Penn Station' / 'To  Washington'.
        """
        origin = re.search(
            r"(?:From|Origin|Departs?(?:\s+from)?)\s*[:\-]?\s*([A-Za-z ]+(?:Station|Terminal)?)",
            text, re.IGNORECASE
        )
        destination = re.search(
            r"(?:To|Dest(?:ination)?|Arrives?(?:\s+at)?)\s*[:\-]?\s*([A-Za-z ]+(?:Station|Terminal)?)",
            text, re.IGNORECASE
        )
        if origin and destination:
            return f"{origin.group(1).strip()} → {destination.group(1).strip()}"

        # Alternative: train name line  "Acela Express 2151 - New York → Washington"
        m = re.search(r"([\w ]+\d+\s*[-–]\s*[\w ]+(?:→|to)[\w ]+)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

        return "Amtrak Trip"

    @staticmethod
    def _extract_ticket_number(text: str) -> Optional[str]:
        m = re.search(
            r"(?:Reservation|Confirmation|Ticket|eTicket)\s*(?:#|No\.?|Number)?\s*[:\-]?\s*([A-Z0-9]{4,12})",
            text, re.IGNORECASE
        )
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_passenger(text: str) -> Optional[str]:
        m = re.search(
            r"(?:Passenger|Traveler|Name)\s*[:\-]?\s*([A-Z][a-z]+ [A-Z][a-z]+)",
            text
        )
        return m.group(1).strip() if m else None


# ── Date helpers ──────────────────────────────────────────────────────────────

def _parse_loose_date(s: str) -> Optional[str]:
    """Parse 'January 15 2024' or 'Jan 15, 2024' → 'YYYY-MM-DD'."""
    from dateutil import parser as dparser
    try:
        return dparser.parse(s).strftime("%Y-%m-%d")
    except Exception:
        return s.strip()


def _normalise_date(s: str) -> Optional[str]:
    """Convert MM/DD/YYYY or YYYY-MM-DD → YYYY-MM-DD."""
    from dateutil import parser as dparser
    try:
        return dparser.parse(s).strftime("%Y-%m-%d")
    except Exception:
        return s.strip()
