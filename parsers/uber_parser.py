"""
Uber Receipt Parser
────────────────────
Parses Uber receipt HTML emails (from noreply@uber.com).

Real email structure observed:
  Subject : "Your [Monday] trip with Uber"  or  "Thanks for tipping, Buyan"
  From    : Uber Receipts <noreply@uber.com>
  Body contains (after HTML stripping):
    "Mar 23, 2026  11:21 AM"    ← trip date/time
    "Thanks for tipping, Buyan"  (or "Thanks for riding, Buyan")
    "Total  $25.72"
    "Conversion 22.23 EUR = 25.72 USD"   ← optional currency note
    "Trip fare  €17.65"          (or "$X.XX" for domestic)
    "Tip  €4.32"
    "Currency conversion fee  $0.30"
    "Fare total  $25.42"

Fields extracted:
  date           – trip date (YYYY-MM-DD)
  amount         – Total in USD (float)
  trip_fare      – fare before tip/fee (string, preserves currency symbol)
  tip            – tip amount (string)
  description    – email subject or constructed summary
  passenger      – first name from greeting
  vendor         – always "Uber"
  source_file    – path of the parsed file
"""

import re
import os
from typing import Dict, Optional

from bs4 import BeautifulSoup


class UberParser:
    VENDOR = "Uber"

    def parse(self, file_path: str) -> Dict:
        text, subject = self._read(file_path)
        return {
            "vendor":      self.VENDOR,
            "date":        self._extract_date(text),
            "amount":      self._extract_total(text),
            "trip_fare":   self._extract_trip_fare(text),
            "tip":         self._extract_tip(text),
            "description": subject or self._build_description(text),
            "passenger":   self._extract_passenger(text),
            "source_file": file_path,
        }

    # ── Reader ────────────────────────────────────────────────────────────────

    @staticmethod
    def _read(path: str):
        """Return (plain_text, subject_line)."""
        ext = os.path.splitext(path)[1].lower()
        subject = None

        if ext in (".html", ".htm"):
            with open(path, "r", errors="replace") as fh:
                raw = fh.read()
            soup = BeautifulSoup(raw, "lxml")
            # Try to grab <title> or first <h1> as subject
            title = soup.find("title")
            h1    = soup.find("h1")
            subject = (title.get_text(strip=True) if title else None) or \
                      (h1.get_text(strip=True) if h1 else None)
            return soup.get_text(separator="\n"), subject

        if ext == ".txt":
            with open(path, "r", errors="replace") as fh:
                text = fh.read()
            # Check if it looks like HTML
            if "<html" in text.lower():
                soup = BeautifulSoup(text, "lxml")
                return soup.get_text(separator="\n"), subject
            return text, subject

        # Fallback plain read
        with open(path, "r", errors="replace") as fh:
            return fh.read(), subject

    # ── Field extractors ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_date(text: str) -> Optional[str]:
        """
        'Mar 23, 2026  11:21 AM'  — Uber puts the trip date near the top.
        Also handles 'March 23, 2026' long form.
        """
        # Short month: "Mar 23, 2026"
        m = re.search(
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s*\d{4}\b",
            text, re.IGNORECASE
        )
        if m:
            return _parse_date(m.group(0))

        # Long month: "March 23, 2026"
        m = re.search(
            r"\b(January|February|March|April|May|June|July|August|"
            r"September|October|November|December)\s+\d{1,2},\s*\d{4}\b",
            text, re.IGNORECASE
        )
        if m:
            return _parse_date(m.group(0))

        return None

    @staticmethod
    def _extract_total(text: str) -> Optional[float]:
        """
        'Total  $25.72'
        When there's currency conversion the USD total is shown first.
        """
        m = re.search(r"\bTotal\b\s*\$\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))

        # Fallback: 'Fare total  $25.42'
        m = re.search(r"Fare\s+total\s*\$\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))

        # Last dollar amount
        amounts = re.findall(r"\$\s*([\d,]+\.\d{2})", text)
        if amounts:
            return float(amounts[-1].replace(",", ""))
        return None

    @staticmethod
    def _extract_trip_fare(text: str) -> Optional[str]:
        """
        'Trip fare  €17.65'  or  'Trip fare  $17.65'
        Preserve the original currency for transparency.
        """
        m = re.search(
            r"Trip\s+fare\s+([€$£¥]?\s*[\d,]+\.\d{2}(?:\s*[A-Z]{3})?)",
            text, re.IGNORECASE
        )
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_tip(text: str) -> Optional[str]:
        """'Tip  €4.32'"""
        m = re.search(
            r"\bTip\b\s+([€$£¥]?\s*[\d,]+\.\d{2}(?:\s*[A-Z]{3})?)",
            text, re.IGNORECASE
        )
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_passenger(text: str) -> Optional[str]:
        """
        'Thanks for tipping, Buyan'  or  'Thanks for riding, Buyan'
        """
        m = re.search(
            r"Thanks\s+for\s+(?:tipping|riding|using\s+Uber)[,\s]+([A-Za-z]+)",
            text, re.IGNORECASE
        )
        return m.group(1).strip() if m else None

    @staticmethod
    def _build_description(text: str) -> str:
        """Construct a short description when no subject is available."""
        date_m = re.search(
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s*\d{4}\b",
            text, re.IGNORECASE
        )
        date_str = date_m.group(0) if date_m else ""
        return f"Uber Trip{' - ' + date_str if date_str else ''}"


# ── Date helper ───────────────────────────────────────────────────────────────

def _parse_date(s: str) -> Optional[str]:
    from dateutil import parser as dparser
    try:
        return dparser.parse(s).strftime("%Y-%m-%d")
    except Exception:
        return s.strip()
