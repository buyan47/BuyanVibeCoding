// ============================================================
//  Travel Receipt Automation — Google Apps Script
//  Last updated: 2026-05-10
//
//  HOW TO USE:
//  1. Go to https://script.google.com → New project
//  2. Paste this entire file into the editor
//  3. Edit the CONFIG section below (dates, folder ID)
//  4. Click Run → main()
//  5. Grant Gmail + Drive + Sheets permissions when prompted (one-time)
//  6. Check Execution Log (View → Logs) for results
//  7. Your spreadsheet appears in the Drive folder automatically
// ============================================================

// ── Configuration ─────────────────────────────────────────────────────────────
var CONFIG = {
  START_MONTH:    '2026-01',   // scan from this month (YYYY-MM)
  END_MONTH:      '2026-04',   // scan to this month inclusive (YYYY-MM)
  DRIVE_FOLDER_ID: '1dh4Va3pawmNb8ZBuaViEa_4-uhItLXl0',  // VibeCodingExperiments/TravelReceipts
  VENDORS: ['amtrak', 'marriott', 'uber'],
  GMAIL_QUERIES: {
    amtrak:   'from:etickets@amtrak.com subject:"SALES RECEIPT"',
    marriott: '(from:marriott.com OR from:email.marriott.com) (subject:"receipt" OR subject:"folio" OR subject:"confirmation")',
    uber:     'from:noreply@uber.com (subject:"trip" OR subject:"tipping" OR subject:"receipt")'
  }
};

// ── Entry point ────────────────────────────────────────────────────────────────
function main() {
  Logger.log('========================================');
  Logger.log('  Travel Receipt Automation');
  Logger.log('  Scanning: ' + CONFIG.START_MONTH + ' → ' + CONFIG.END_MONTH);
  Logger.log('========================================');

  var startDate = firstDay(CONFIG.START_MONTH);
  var endDate   = lastDay(CONFIG.END_MONTH);
  var allRecords = [];

  CONFIG.VENDORS.forEach(function(vendor) {
    var baseQuery = CONFIG.GMAIL_QUERIES[vendor];
    if (!baseQuery) { Logger.log('No query for ' + vendor + ', skipping.'); return; }

    var query = baseQuery
      + ' after:'  + fmtDate(startDate)
      + ' before:' + fmtDate(endDate);

    Logger.log('\nSearching ' + vendor.toUpperCase() + '...');
    Logger.log('Query: ' + query);

    var threads = GmailApp.search(query, 0, 200);
    Logger.log('Found ' + threads.length + ' thread(s).');

    threads.forEach(function(thread) {
      thread.getMessages().forEach(function(msg) {
        var rec = parseMessage(msg, vendor);
        if (rec) {
          Logger.log('  ✓ [' + vendor + '] ' + rec.date + '  $' + (rec.amount || '?') + '  ' + (rec.description || '').slice(0, 50));
          allRecords.push(rec);
        }
      });
    });
  });

  Logger.log('\n----------------------------------------');
  Logger.log('Total receipts parsed: ' + allRecords.length);

  if (allRecords.length === 0) {
    Logger.log('No receipts found. Check your date range and Gmail queries.');
    return;
  }

  var url = writeToSheet(allRecords);
  Logger.log('\n✅ Done!');
  Logger.log('Spreadsheet: ' + url);
  Logger.log('Location: My Drive → VibeCodingExperiments → TravelReceipts');
}

// ── Message parser dispatcher ──────────────────────────────────────────────────
function parseMessage(msg, vendor) {
  var subject   = msg.getSubject();
  var date      = msg.getDate();
  var plainBody = msg.getPlainBody() || '';
  var htmlBody  = msg.getBody()      || '';

  // Prefer plain text; fall back to HTML stripped of tags
  var text = plainBody.length > 100 ? plainBody : htmlBody.replace(/<[^>]+>/g, ' ');

  var base = {
    vendor:      vendor,
    date:        Utilities.formatDate(date, Session.getScriptTimeZone(), 'yyyy-MM-dd'),
    subject:     subject,
    amount:      null,
    description: subject,
    notes:       ''
  };

  if (vendor === 'amtrak')   return parseAmtrak(text, base);
  if (vendor === 'marriott') return parseMarriott(text, base);
  if (vendor === 'uber')     return parseUber(text, base);
  return base;
}

// ── Amtrak parser ──────────────────────────────────────────────────────────────
function parseAmtrak(text, rec) {
  // Amount — try most specific pattern first
  var m = text.match(/Total\s+Charged\s+by\s+Amtrak\s*\$?\s*([\d,]+\.\d{2})/i)
       || text.match(/\bTotal\b\s*\$?\s*([\d,]+\.\d{2})/i);
  if (!m) { var all = text.match(/\$([\d,]+\.\d{2})/g); if (all) m = [null, all[all.length-1].replace('$','')]; }
  if (m) rec.amount = parseFloat(m[1].replace(/,/g, ''));

  // Route description
  var route = text.match(/([A-Za-z ]+,\s*[A-Z]{2}\s+to\s+[A-Za-z ]+)/i);
  if (route) rec.description = route[1].trim().replace(/\s+to\s+/i, ' → ');

  // Reservation number
  var res = text.match(/Reservation\s+(?:Number\s*)?[-–:]?\s*([A-Z0-9]{4,12})/i);
  if (res) rec.notes = 'Res# ' + res[1];

  // Passenger
  var pax = text.match(/Passengers?\s*\n+\s*([A-Z][a-z]+ [A-Z][a-z]+)/);
  if (pax) rec.notes += (rec.notes ? ' | ' : '') + pax[1];

  return rec;
}

// ── Marriott parser ────────────────────────────────────────────────────────────
function parseMarriott(text, rec) {
  // Amount
  var m = text.match(/\*+\s*Total\s+([\d,]+\.\d{2})/i);
  if (!m) { var all = text.match(/\b([\d,]+\.\d{2})\b/g); if (all) m = [null, all[all.length-1]]; }
  if (m) rec.amount = parseFloat(m[1].replace(/,/g, ''));

  // Property name — look in first 30 lines for a Marriott brand name
  var lines = text.split('\n').slice(0, 30);
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim();
    if (/Marriott|Courtyard|Sheraton|Westin|Renaissance|Residence Inn|Fairfield|Autograph|Aloft|Moxy/i.test(line)
        && line.length > 5
        && !/copyright|bonvoy|reserved/i.test(line)) {
      rec.description = line;
      break;
    }
  }

  // Check-in / check-out
  var ci = text.match(/Arrive\s+Date\s+(\d{1,2}-[A-Z]{3}-\d{2,4})/i);
  var co = text.match(/Depart\s+Date\s+(\d{1,2}-[A-Z]{3}-\d{2,4})/i);
  if (ci) rec.notes = 'In: ' + ci[1];
  if (co) rec.notes += (rec.notes ? ' | ' : '') + 'Out: ' + co[1];

  return rec;
}

// ── Uber parser ────────────────────────────────────────────────────────────────
function parseUber(text, rec) {
  // Total
  var m = text.match(/\bTotal\b\s*\$([\d,]+\.\d{2})/i)
       || text.match(/Fare\s+total\s*\$([\d,]+\.\d{2})/i);
  if (m) rec.amount = parseFloat(m[1].replace(/,/g, ''));

  // Tip
  var tip = text.match(/\bTip\b\s*\$?([\d,]+\.\d{2})/i);
  if (tip) rec.notes = 'Tip: $' + tip[1];

  // Date from body as description
  var d = text.match(/\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s*\d{4}\b/i);
  if (d) rec.description = 'Uber Trip - ' + d[0];

  return rec;
}

// ── Google Sheets writer ───────────────────────────────────────────────────────
function writeToSheet(records) {
  var ts = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyyMMdd_HHmmss');
  var ss = SpreadsheetApp.create('travel_receipts_' + ts);

  // ── Summary sheet ──────────────────────────────────────────────────────────
  var summary = ss.getActiveSheet();
  summary.setName('Summary');
  buildSheet(summary, records, ['Vendor','Date','Amount ($)','Description','Notes']);

  // ── Per-vendor sheets ──────────────────────────────────────────────────────
  var vendors = ['amtrak', 'marriott', 'uber'];
  var colors  = { amtrak: '#215FA8', marriott: '#B11116', uber: '#000000' };

  vendors.forEach(function(v) {
    var rows = records.filter(function(r) { return r.vendor === v; });
    if (rows.length === 0) return;
    var sheet = ss.insertSheet(v.charAt(0).toUpperCase() + v.slice(1));
    buildSheet(sheet, rows, ['Vendor','Date','Amount ($)','Description','Notes'], colors[v]);
  });

  // Move to Drive folder
  var file   = DriveApp.getFileById(ss.getId());
  var folder = DriveApp.getFolderById(CONFIG.DRIVE_FOLDER_ID);
  folder.addFile(file);
  try { DriveApp.getRootFolder().removeFile(file); } catch(e) {}

  return ss.getUrl();
}

function buildSheet(sheet, records, headers, headerColor) {
  headerColor = headerColor || '#2E4057';

  // Header row
  sheet.appendRow(headers);
  var hdr = sheet.getRange(1, 1, 1, headers.length);
  hdr.setBackground(headerColor).setFontColor('#FFFFFF').setFontWeight('bold');
  sheet.setFrozenRows(1);

  // Data rows
  records.forEach(function(rec) {
    sheet.appendRow([
      rec.vendor      || '',
      rec.date        || '',
      rec.amount      || '',
      rec.description || '',
      rec.notes       || ''
    ]);
  });

  // Format amount column (column 3)
  if (records.length > 0) {
    sheet.getRange(2, 3, records.length, 1).setNumberFormat('"$"#,##0.00');
  }

  // Total row
  var lastRow = records.length + 2;
  sheet.getRange(lastRow, 1).setValue('TOTAL').setFontWeight('bold');
  sheet.getRange(lastRow, 3)
    .setFormula('=SUM(C2:C' + (lastRow - 1) + ')')
    .setFontWeight('bold')
    .setNumberFormat('"$"#,##0.00');

  sheet.autoResizeColumns(1, headers.length);
}

// ── Date helpers ───────────────────────────────────────────────────────────────
function firstDay(ym) {
  var p = ym.split('-');
  return new Date(parseInt(p[0]), parseInt(p[1]) - 1, 1);
}

function lastDay(ym) {
  var p = ym.split('-');
  return new Date(parseInt(p[0]), parseInt(p[1]), 0);
}

function fmtDate(d) {
  return Utilities.formatDate(d, 'UTC', 'yyyy/MM/dd');
}
