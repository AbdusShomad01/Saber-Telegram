# 📖 Panduan Membaca Sinyal & Laporan Saber Trader AI Signal Bot

Saber Trader AI Signal Bot dirancang untuk membantu Anda menganalisis pasar saham Indonesia (IDX) dengan menggabungkan analisis teknikal klasik, pola chart/candle, aliran dana institusi (**Bandarmology** & **Foreign Flow**), serta analisis visual grafik berbasis AI (**Gemini**).

Berikut adalah panduan lengkap cara membaca pesan laporan sinyal yang dikirimkan oleh bot ke Telegram.

---

## 1. Status Sinyal (Signal) & Emojinya
Setiap saham yang berhasil lolos pemindaian akan dikategorikan ke dalam salah satu status berikut:

| Sinyal | Emoji | Penjelasan | Tindakan |
| :--- | :---: | :--- | :--- |
| **STRONG BUY** | 🟢🟢 | Momentum sangat kuat, volume di atas rata-rata, dan didukung akumulasi Bandar/Asing yang signifikan. | Sangat disarankan untuk masuk dengan rencana trading ketat. |
| **BUY** | 🟢 | Tren naik terkonfirmasi, indikator mendukung kelanjutan tren. | Beli di area harga entry yang direkomendasikan. |
| **WATCHLIST** | 🟡 | Saham menarik dengan pola bagus, namun harga sedang berada di area resistensi atau butuh koreksi sehat. | Tunggu di harga diskon (*Buy on Weakness*) atau beli saat konfirmasi rebound (*Buy on Strength*). |
| **AVOID** | 🟠 | Saham memiliki likuiditas buruk, tren turun kuat, atau distribusi bandar yang masif. | Hindari transaksi pada saham ini. |
| **SELL** | 🔴 | Sinyal jual terkonfirmasi karena penembusan support kunci atau pembalikan tren ke arah bearish. | Jual atau ambil keuntungan (*Take Profit*). |

---

## 2. Parameter Pasar & Analisis Tren
*   **🌍 IHSG Regime**: Menunjukkan kondisi tren pasar saham gabungan secara keseluruhan sebagai **alat informasi dan wawasan konteks makro** (tidak mengurangi ataupun memodifikasi skor sinyal saham):
    *   🟢 **BULLISH**: Pasar IHSG sedang tren naik.
    *   🟡 **SIDEWAYS**: Pasar IHSG bergerak mendatar.
    *   🔴 **BEARISH**: Pasar IHSG sedang tren turun. Saham dengan setup teknikal & akumulasi bandar yang bagus tetap dapat memicu sinyal BUY tanpa dipotong skornya oleh IHSG.
*   **📊 Daily Trend**: Menampilkan tren harian saham. Sangat penting saat membaca sinyal **intraday** (misal chart 60 menit) untuk memastikan Anda tidak membeli saham yang tren besarnya (harian) masih bearish kuat (*trend crosscheck*).

### 2.1 Filter Eliminasi Otomatis (Hard Filters)
Sebelum saham dinilai (*scoring*), sistem menerapkan filter awal untuk membuang saham berisiko:
1.  **Harga Saham Minimal (> Rp 10)**: Saham dengan harga penutupan terakhir **> Rp 10 tetap dimasukkan** ke dalam radar pemindaian. Filter restriksi FCA (*Full Call Auction*) telah ditiadakan sehingga seluruh saham aktif di atas Rp 10 tetap diproses. Hanya saham tidur/berisiko ekstrem dengan harga $\le$ Rp 10 yang dikeluarkan.
2.  **Saham Naik > 15% Kemarin**: Saham yang sudah melonjak > 15% pada hari perdagangan sebelumnya langsung dikeluarkan dari kandidat (mencegah risiko membeli di pucuk *climax run*, aksi *profit taking* tajam, atau risiko suspensi bursa).
3.  **Threshold Likuiditas**:
    *   **Daily (1d)**: Rata-rata volume 20 hari minimal **5.000 lot** (500.000 lembar) dan nilai transaksi rata-rata minimal **Rp 2 Miliar/hari** (dilonggarkan dari sebelumnya 10.000 lot & Rp 5 Miliar agar lebih banyak saham second-liner potensial tersaring).
    *   **Intraday (60m)**: Minimal 1.000 lot dan nilai transaksi Rp 1 Miliar.
4.  **Filter Volatilitas & Tren**:
    *   **ADX**: ADX dinilai secara berjenjang (0–3 poin) pada kategori *Trend & Momentum* dan **tidak lagi menggugurkan saham secara mutlak**. Saham yang sedang berada di fase akumulasi awal atau konsolidasi (*base building* sebelum *breakout*) tetap dapat lolos seleksi.
    *   **ATR > 7%**: Saham dengan volatilitas harian ekstrem dieliminasi demi keamanan manajemen risiko modal.

> [!NOTE]
> **Kebijakan Kuota & AI Guard Terbaru**:
> - **Tanpa Batasan Kuota Top 10 & Sektor**: Seluruh saham yang memenuhi kriteria *bullish* (*STRONG BUY, BUY, WATCHLIST*) akan dikirimkan ke Telegram tanpa batasan maksimal 10 saham atau maksimal 3 saham per sektor.
> - **AI Guard (Pagi & Siang)**: Sinyal teknikal/kuantitatif *BUY, STRONG BUY, atau WATCHLIST* dilindungi oleh *AI Guard* sehingga tidak akan dibatalkan/di-*downgrade* menjadi *AVOID* oleh AI Vision. Analisis visual AI tetap disajikan secara lengkap sebagai panduan catatan risiko.

---

## 3. Skor Penilaian & Keyakinan
*   **📊 Score (XX/100)**: Skor kuantitatif deterministik dari indikator teknikal, likuiditas, volume, pola chart, dan bandarmologi/foreign flow:
    *   `90 - 100`: **STRONG BUY** (Setup sangat istimewa)
    *   `75 - 89`: **BUY** (Setup solid & layak beli)
    *   `55 - 74`: **WATCHLIST** (Menarik, tunggu konfirmasi/diskon)
    *   `< 55`: **AVOID** (Kurang mendukung / berisiko)
*   **🎯 Confidence (X/10)**: Tingkat keyakinan visual model AI (Gemini) setelah membaca gambar grafik teknikal secara langsung:
    *   `8 - 10`: **VERY HIGH** / **HIGH CONVICTION** (Sinyal sangat valid secara teknikal & visual).
    *   `5 - 7`: **MEDIUM** (Cukup bagus, namun ada beberapa resistensi visual).
    *   `< 5`: **LOW** (Risiko tinggi atau chart kurang rapi).

---

## 4. Manajemen Risiko & Rencana Trading (Risk Management)
Untuk sinyal **BUY** dan **STRONG BUY**, bot akan memberikan panduan harga masuk dan target keluar bertahap:

```text
💰 Risk Management
├─ Entry          : Rp6,150          <-- Harga masuk yang ideal
├─ TP1 (exit 50%) : Rp6,350          <-- Target 1 (jual setengah porsi)
├─ TP2 (exit 30%) : Rp6,550          <-- Target 2 (jual 30% porsi)
├─ TP3 (hold 20%) : Rp6,800          <-- Target 3 (jual sisa porsi jika tren berlanjut)
├─ SL ATR         : Rp5,950          <-- Stop Loss berbasis volatilitas (Average True Range)
├─ SL Moderat     : Rp5,900          <-- Stop Loss toleransi menengah (Support terdekat)
├─ SL Konservatif : Rp5,800          <-- Stop Loss toleransi longgar (Support kuat)
└─ R:R Ratio      : 2.10             <-- Rasio Risk/Reward (Minimal > 1.5)
```

> [!TIP]
> **Strategi Exit Bertahap (Partial Profit Taking):**
> Menjual sebagian posisi di TP1 dan TP2 bertujuan untuk mengunci profit awal, sehingga jika harga tiba-tiba berbalik arah, Anda tidak mengalami kerugian secara keseluruhan.

---

## 5. Analisis Fibonacci (Khusus Sinyal WATCHLIST)
Untuk saham dengan status **WATCHLIST**, bot menggunakan analisis Fibonacci retracement otomatis:

*   **Swing Low & Swing High**: Rentang harga terendah dan tertinggi yang digunakan untuk menarik garis Fibonacci.
*   **Opsi Entry 1: Buy on Weakness (Discount)**: Direkomendasikan jika harga sekarang sudah terkoreksi ke area diskon (di bawah Fib level 0.618). Anda bisa langsung membeli di harga pasar saat ini dengan target stop loss yang lebih rapat.
*   **Opsi Entry 2: Buy on Strength (Konfirmasi)**: Direkomendasikan jika Anda ingin menunggu harga terkonfirmasi memantul kembali ke atas level Fib 0.618 sebelum melakukan pembelian.

---

## 6. Rincian Poin Analisis (Score Breakdown)
Sistem penilaian (*scoring*) memiliki total **100 poin (100%)** yang terbagi dalam 3 pilar utama:
- 📊 **Analisis Teknikal**: **75% (75 poin)**
- 🏦 **Analisa Broker Summary (Bandarmology)**: **15% (15 poin)**
- 🌐 **Analisa Foreign Flow**: **10% (10 poin)**

### Distribusi Poin Analisis (8 Engines):
1.  **Trend & Momentum (Maks 21 poin)**: Mengukur arah tren menggunakan moving averages (EMA10, EMA20, EMA50) dan indikator momentum (RSI, MACD, ADX, VWAP).
2.  **Volume & Liquidity (Maks 20 poin)**: Menilai lonjakan volume breakout (≥2x Avg20), perbandingan volume 5H vs 20H, buying/selling pressure, serta likuiditas nilai transaksi harian.
3.  **Pattern & Candle (Maks 10 poin)**: Skor konfirmasi pola chart bullish (*Double Bottom, Cup & Handle, Bullish Flag*, dll.) dan candlestick reversal.
4.  **Gap Analysis (Maks 5 poin)**: Mendeteksi gap up terkonfirmasi volume atau gap down berisiko.
5.  **Sector Correlation (Maks 4 poin)**: Mengukur relative strength pergerakan saham dibandingkan indeks IHSG (outperform/underperform).
6.  **Support/Resistance & Risk-Reward (Maks 15 poin)**: Menilai kedekatan harga dengan support kunci (Bollinger Band, Stochastic oversold) serta optimalitas rasio Risk/Reward (ATR, OBV).
7.  **Broker Summary / Bandarmology (Maks 15 poin)**: Menilai akumulasi/distribusi smart money, profil broker pembeli elite (AK, RX, DP, dll.), dominasi broker asing, dan winning broker combo.
8.  **Foreign Flow (Maks 10 poin)**: Menilai volume akumulasi/distribusi bersih dari investor asing (*net foreign buy/sell*).

---

## 7. Aliran Dana (Bandarmology & Foreign Flow)
*   **🏦 Bandarmology**: Menampilkan kondisi akumulasi Bandar berdasarkan konsentrasi transaksi broker:
    *   `Big Accumulation` / `Small Accumulation`: Bandar sedang mengumpulkan barang (sangat bullish).
    *   `Neutral`: Distribusi dan akumulasi relatif seimbang.
    *   `Big Distribution` / `Small Distribution`: Bandar sedang melepas kepemilikan barang (bearish).
    *   **Top Buyers / Top Sellers**: Kode broker lokal beserta jumlah volume lot akumulasi/distribusi hari ini (contoh: <code>- XL : 500 lot</code>).
*   **🌐 Foreign Flow**: Aliran dana investor asing secara akumulatif. Saham blue-chip sangat dipengaruhi oleh partisipasi bersih asing (*Net Buy* / *Net Sell*).

---

## 8. Berita Terkait & Opini Analis AI
*   **📰 Berita Terkait**: Menampilkan tajuk berita terbaru untuk mendeteksi sentimen fundamental atau katalis penggerak harga saham.
*   **💡 Opini Analis**: Merupakan penjelasan langsung dari **Strategi AI Agent** (Gemini) yang merangkum hasil analisis visual chart, kecocokan indikator teknikal dengan data bandarmology, serta keputusan akhir mengapa saham tersebut layak dibeli beserta mitigasi risikonya.

---
*Disclaimer: Analisis yang dihasilkan oleh bot bersifat informatif untuk membantu keputusan trading Anda secara mandiri. Selalu lakukan analisis pribadi kembali (DYOR - Do Your Own Research).*
