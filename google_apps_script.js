/**
 * ====================================================================
 * SABER TRADER — GOOGLE APPS SCRIPT FOR SIGNAL RECAP (SPS)
 * ====================================================================
 * 
 * CARA MEMASANG DI GOOGLE SPREADSHEET:
 * 1. Buat Spreadsheet baru di Google Drive (https://sheets.new)
 * 2. Beri nama spreadsheet, misalnya: "Saber Trader — Rekap Sinyal Saham"
 * 3. Klik menu: Extensions (Ekstensi) > Apps Script
 * 4. Hapus semua kode default di editor, lalu PASTE SELURUH KODE DI BAWAH INI.
 * 5. Klik icon Save (Simpan).
 * 6. Klik tombol "Deploy" (Terapkan) di kanan atas > "New deployment" (Penerapan baru).
 * 7. Pada icon Gerigi/Select type, pilih "Web app".
 * 8. Atur konfigurasinya:
 *    - Description: Webhook Rekap Sinyal
 *    - Execute as: Me (email akun Google Anda)
 *    - Who has access: Anyone (Siapa saja)  <-- PENTING agar bot bisa mengirim data
 * 9. Klik "Deploy", lalu klik "Authorize access" dan izinkan akun Anda.
 * 10. Salin "Web app URL" (akhiran /exec).
 * 11. Masukkan ke file .env di bot:
 *     GOOGLE_SHEET_WEBHOOK_URL=https://script.google.com/macros/s/.../exec
 *     GOOGLE_SHEET_VIEW_URL=https://docs.google.com/spreadsheets/d/.../edit
 * ====================================================================
 */

function doPost(e) {
  try {
    var rawContents = e.postData.contents;
    var payload = JSON.parse(rawContents);
    var signals = payload.signals || [];
    var summary = payload.summary || {};
    var updatedAt = payload.updated_at || new Date().toLocaleString("id-ID", { timeZone: "Asia/Jakarta" });

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getActiveSheet();
    sheet.setName("Rekap Sinyal");

    // 1. Bersihkan isi sheet
    sheet.clear();

    // 2. Judul & Info Update
    sheet.getRange("A1").setValue("📊 REKAPITULASI SINYAL SAHAM IDX — SABER TRADER");
    sheet.getRange("A1").setFontSize(14).setFontWeight("bold").setFontColor("#1A365D");

    sheet.getRange("A2").setValue("Terakhir Diperbarui: " + updatedAt + " | Total Sinyal: " + signals.length + " | Winrate Selesai: " + (summary.resolved_winrate || 0) + "%");
    sheet.getRange("A2").setFontSize(10).setFontStyle("italic").setFontColor("#555555");

    // 3. Header Tabel
    var headers = [
      "No",
      "Tanggal Sinyal",
      "Ticker",
      "Timeframe",
      "Sinyal",
      "Skor",
      "Harga Entry",
      "Harga Terakhir / Exit",
      "Target TP1",
      "Target TP2",
      "Stop Loss",
      "P&L (%)",
      "Status Sinyal"
    ];

    var startRow = 4;
    var headerRange = sheet.getRange(startRow, 1, 1, headers.length);
    headerRange.setValues([headers]);
    headerRange.setFontWeight("bold");
    headerRange.setBackground("#1A365D");
    headerRange.setFontColor("#FFFFFF");
    headerRange.setHorizontalAlignment("center");
    headerRange.setVerticalAlignment("middle");

    if (signals.length === 0) {
      sheet.getRange("A5").setValue("Belum ada data sinyal.");
      return ContentService.createTextOutput(JSON.stringify({ status: "success", count: 0 }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // 4. Siapkan Baris Data
    var rows = [];
    for (var i = 0; i < signals.length; i++) {
      var s = signals[i];
      rows.push([
        s.no,
        s.date,
        s.ticker,
        s.timeframe,
        s.signal,
        s.score,
        s.entry_price,
        s.current_price,
        s.tp1,
        s.tp2,
        s.stop_loss,
        (s.pnl_pct / 100), // Format persentase di Google Sheets
        s.status
      ]);
    }

    var dataRange = sheet.getRange(startRow + 1, 1, rows.length, headers.length);
    dataRange.setValues(rows);

    // 5. Format Angka & Tampilan
    sheet.getRange(startRow + 1, 1, rows.length, 1).setHorizontalAlignment("center"); // No
    sheet.getRange(startRow + 1, 2, rows.length, 1).setHorizontalAlignment("center"); // Tanggal
    sheet.getRange(startRow + 1, 3, rows.length, 1).setHorizontalAlignment("center").setFontWeight("bold"); // Ticker
    sheet.getRange(startRow + 1, 4, rows.length, 1).setHorizontalAlignment("center"); // Timeframe
    sheet.getRange(startRow + 1, 5, rows.length, 1).setHorizontalAlignment("center"); // Sinyal
    sheet.getRange(startRow + 1, 6, rows.length, 1).setHorizontalAlignment("right").setNumberFormat("0.0"); // Skor

    // Harga Rupiah
    var priceRange = sheet.getRange(startRow + 1, 7, rows.length, 5); // Entry, Current, TP1, TP2, SL
    priceRange.setNumberFormat('"Rp "#,##0');
    priceRange.setHorizontalAlignment("right");

    // Format P&L Persentase
    var pnlRange = sheet.getRange(startRow + 1, 12, rows.length, 1);
    pnlRange.setNumberFormat('+0.00%;-0.00%;0.00%');
    pnlRange.setHorizontalAlignment("right").setFontWeight("bold");

    // Format Status Sinyal dengan Pewarnaan
    var statusRange = sheet.getRange(startRow + 1, 13, rows.length, 1);
    statusRange.setHorizontalAlignment("center").setFontWeight("bold");

    for (var r = 0; r < rows.length; r++) {
      var curRow = startRow + 1 + r;
      var statusVal = String(rows[r][12]);
      var cell = sheet.getRange(curRow, 13);
      var pnlCell = sheet.getRange(curRow, 12);

      if (statusVal.indexOf("TP") !== -1) {
        // TP Hit: Hijau Kuat
        cell.setBackground("#D4EDDA").setFontColor("#155724");
        pnlCell.setFontColor("#155724");
      } else if (statusVal.indexOf("SL") !== -1) {
        // SL Hit: Merah Kuat
        cell.setBackground("#F8D7DA").setFontColor("#721C24");
        pnlCell.setFontColor("#721C24");
      } else if (statusVal.indexOf("Profit") !== -1) {
        // Floating Profit: Hijau Lembut
        cell.setBackground("#E8F5E9").setFontColor("#2E7D32");
        pnlCell.setFontColor("#2E7D32");
      } else if (statusVal.indexOf("Loss") !== -1) {
        // Floating Loss: Merah Lembut
        cell.setBackground("#FFEBEE").setFontColor("#C62828");
        pnlCell.setFontColor("#C62828");
      } else {
        // Expired / BEP: Abu-abu
        cell.setBackground("#F5F5F5").setFontColor("#616161");
      }

      // Zebra striping lembut untuk kolom data lainnya
      if (r % 2 === 1) {
        sheet.getRange(curRow, 1, 1, 11).setBackground("#F8FAFC");
      }
    }

    // 6. Freeze Header & Auto Resize Column
    sheet.setFrozenRows(4);
    for (var col = 1; col <= headers.length; col++) {
      sheet.autoResizeColumn(col);
    }

    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      rows_written: rows.length,
      updated_at: updatedAt
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "ok",
    message: "Saber Trader Google Sheet Webhook is active and ready to receive POST data."
  })).setMimeType(ContentService.MimeType.JSON);
}
