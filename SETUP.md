# Travel Receipt Automation — Setup Guide

## Prerequisites
- Python 3.9+
- A Google account with Gmail and Google Drive

---

## Step 1 — Enable Google APIs

1. Go to https://console.cloud.google.com/
2. Create a new project (e.g. *TravelReceipts*)
3. Enable these two APIs:
   - **Gmail API**
   - **Google Drive API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Choose **Desktop App**, give it a name, click **Create**
6. Click **Download JSON** and rename the file to `credentials.json`
7. Place `credentials.json` in this project directory

---

## Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

---

## Step 3 — First run (browser auth)

The first time you run the script a browser window will open asking you to
grant access to your Gmail and Drive.  After you approve, a `token.json` file
is saved locally so you won't be asked again.

---

## Step 4 — Run the script

```bash
# Scan Jan–Mar 2024, parse Amtrak + Marriott, upload to Drive, export Excel+CSV
python main.py --start 2024-01 --end 2024-03

# Custom date range with all vendors
python main.py --start 2024-06 --end 2024-12 --vendors amtrak marriott uber

# Skip Drive upload (just parse and export locally)
python main.py --start 2024-01 --end 2024-06 --skip-drive

# Parse files you already downloaded (no Gmail needed)
python main.py --parse-only downloads/
```

---

## Output

| File | Location | Contents |
|------|----------|----------|
| `travel_receipts_<timestamp>.xlsx` | `output/` | One sheet per vendor + Summary sheet with totals |
| `travel_receipts_<timestamp>.csv`  | `output/` | Flat CSV with all records |
| Raw attachments | `downloads/` | Original PDFs / HTML from Gmail |
| Copies in Drive | `My Drive / Travel Receipts / <Vendor>/` | Uploaded automatically |

---

## Excel columns

### Amtrak sheet
| Column | Description |
|--------|-------------|
| Vendor | "Amtrak" |
| Date | Travel date (YYYY-MM-DD) |
| Amount ($) | Total charged |
| Description | Route (e.g. New York → Washington DC) |
| Ticket # | Amtrak confirmation number |
| Passenger | Traveler name |

### Marriott sheet
| Column | Description |
|--------|-------------|
| Vendor | "Marriott" |
| Date | Check-in date (YYYY-MM-DD) |
| Amount ($) | Total charged |
| Description | Hotel property name |
| Check-Out | Check-out date |
| Nights | Number of nights |
| Confirm # | Reservation confirmation number |

---

## Customising Gmail search queries

Edit `config.py` → `GMAIL_QUERIES` to tighten the searches, for example:

```python
"amtrak": 'from:noreply@amtrak.com subject:"eTicket"',
"marriott": 'from:marriott@marriott.com subject:"Folio"',
```
