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
Setiap indikator berkontribusi terhadap total skor dengan bobot sebagai berikut:
1.  **Trend & Momentum (Maks 25 poin)**: Mengukur arah tren menggunakan moving averages (EMA20, EMA50) dan indikator momentum (RSI, MACD, ADX).
2.  **Volume & Liquidity (Maks 15 poin)**: Menilai apakah saham memiliki volume transaksi yang cukup likuid untuk keluar-masuk dengan mudah.
3.  **Pattern (Maks 15 poin)**: Skor tambahan jika terdeteksi pola grafik bullish (*Double Bottom, Cup & Handle, Bullish Flag*, dll.).
4.  **Support/Resistance (Maks 10 poin)**: Menilai kedekatan harga dengan support kunci (semakin dekat support, semakin baik skor risikonya).
5.  **Bandarmology (Maks 15 poin)**: Menilai akumulasi/distribusi dari top broker lokal.
6.  **Foreign Flow (Maks 10 poin)**: Menilai volume akumulasi bersih dari investor asing.
7.  **Risk/Reward (Maks 10 poin)**: Menilai perbandingan potensi profit dibanding potensi rugi.

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
