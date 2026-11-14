---
name: kantor-ai-3-agen
description: Bikin Kantor AI 3D dengan 3 agen (riset, admin, konten) dari template kantor-ai-template, lalu sambungkan laporan harian agen ke kantornya. Pakai saat diminta "buat kantor AI", "kantor 3 agen", "AI agent kantor 3D", atau menyesuaikan kantor untuk bisnis sendiri.
---

# Kantor AI 3 Agen

Tujuan: dalam satu sesi, pengguna punya kantor 3D berisi 3 agen yang namanya, tugasnya, jadwalnya, dan laporannya
sesuai bisnisnya sendiri, bisa dibuka di browser dan direkam jadi video.

## 0. Tanya dulu (maksimal 4 pertanyaan, sekaligus)
1. Nama kantor/bisnis.
2. Bidang usaha (mis. katering, toko online, jasa desain).
3. Nama untuk 3 agen (boleh "terserah").
4. Gaya 3D: asli, clay, voxel, hologram, angkringan, dll. (default `asli`).

Kalau pengguna bilang "terserah", pakai preset di bawah dan lanjut.

## 1. Siapkan proyek
```bash
git clone https://github.com/malikisaputra-source/kantor-ai-template.git kantor-ai
cd kantor-ai && npm install
```
Butuh Node.js 18+. Kalau `npm` belum ada, minta pengguna pasang Node.js dulu dari nodejs.org.

## 2. Ubah ke 3 agen (hanya `src/config.ts` dan `src/laporan.json`)
Tiga peran dasar, satu per ruangan:

| Ruangan | Agen | Tugas | Contoh pekerjaan harian |
|---|---|---|---|
| `bizdev` (label: Riset) | Agen riset | Cari peluang | cek tender/kompetitor/tren, rangkum 3 temuan |
| `keuangan` (label: Admin) | Agen admin | Email & dokumen | rapikan inbox, buat draf invoice/balasan |
| `studio` (label: Konten) | Agen konten | Ide & desain | 3 ide konten, draf caption, brief desain |

Preset `AGEN` (tengah tiap ruangan, aman tidak bertumpuk):
```ts
export const AGEN: Agen[] = [
  { key: 'riset', nama: 'Rani', tugas: 'Cari peluang', ruang: 'bizdev', warna: '#e4572e', x: -4.4, z: -0.2 },
  { key: 'admin', nama: 'Dimas', tugas: 'Email & dokumen', ruang: 'keuangan', warna: '#f2b134', x: 0.1, z: -0.2 },
  { key: 'konten', nama: 'Laras', tugas: 'Ide & desain', ruang: 'studio', warna: '#3a86ff', x: 4.5, z: -0.2 },
];
```
- Ganti `label` di `RUANGAN` jadi Riset / Admin / Konten (key-nya biarkan).
- `JADWAL`: ganti key agen lama (`raka`, `sekar`, `gilang`, `riska`) dengan `riset`, `admin`, `konten`. Hapus baris yang agennya sudah tidak ada. Baris `agen: '*'` biarkan.
- `src/laporan.json`: kosongkan isinya, lalu buat tepat 3 kunci `riset`, `admin`, `konten` dengan `ringkasan`, `menunggu`, `mendesak`, dan `angka` yang sesuai bidang usaha pengguna.
- `KANTOR.nama` dan `KANTOR.subjudul` diisi nama bisnis pengguna. `GAYA` diisi pilihan gaya.

## 3. Cek
```bash
npm test && npm run build
npm run dev   # buka http://localhost:5173  ·  ?timelapse=1 untuk satu hari dipercepat
```
Buka di browser. Pastikan 3 agen muncul, tidak ada meja bertumpuk, dan gelembung laporan terbaca. Kalau tes
menyebut nama agen lama, sesuaikan tesnya dengan key baru, jangan hapus tesnya.

## 4. Sambungkan agen asli (opsional)
Agen sungguhan (Claude Code, Codex, n8n, skrip cron) cukup menulis ulang `src/laporan.json` setiap selesai kerja,
dengan format yang sama. Contoh perintah untuk agen riset:
> "Cari 3 peluang baru untuk [bisnis]. Tulis hasilnya ke src/laporan.json pada kunci `riset`: ringkasan satu kalimat,
> `menunggu` untuk yang perlu keputusanku, `angka` jumlah temuan."

Kantor membaca file itu saat dimuat ulang.

## 5. Rekam video (opsional)
```bash
npm run rekam -- kantor.mp4
```
Set `TAMPIL_PEMILIH_GAYA = false` sebelum merekam video final.

## Aturan
- Jangan menulis nominal uang, nomor rekening, atau data pribadi di `laporan.json` kalau videonya mau dibagikan.
- Jangan menambah teks, klaim, atau janji ke klien di layar yang tidak diminta pengguna.
- Bentuk 3D tetap sederhana (lihat AGENTS.md). Jangan menambah model/aset luar.
- Selesai = `npm test` lulus, build sukses, dan kantor sudah dilihat di browser.


---
<!-- kredit-maliki -->
**Kredit:** Template oleh Maliki Saputra (@malikisaputra) — https://malikisaputra.biz.id.
**Lisensi Nonkomersial Maliki Studio:** gratis untuk belajar & usaha/organisasi sendiri. Dilarang dijual, dijual ulang, atau dipakai untuk jasa berbayar. Kredit wajib dipertahankan. Lihat `LICENSE`.
