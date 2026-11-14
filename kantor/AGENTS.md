# Aturan untuk agen AI (Claude Code, Codex, Antigravity, dll.)

Template Kantor AI 3D: React + Vite + Three.js. `CLAUDE.md` dan `GEMINI.md` hanya merujuk ke file ini.

## Struktur
- `src/config.ts`: nama kantor, ruangan, agen, jadwal, babak timelapse. Hampir semua perubahan cukup di sini.
- `src/laporan.json`: laporan agen hari ini (ringkasan, menunggu, mendesak, angka). Agen boleh menulis file ini.
- `src/office.ts`: logika (jadwal → status, timelapse, agen santai). Fungsi murni, dites di `scripts/test.mjs`.
- `src/gaya/`: 16 gaya 3D + asli (`alat.ts` = tipe Kit & helper, `kakilima.ts` = tekstur & perabot gaya kaki lima, `daftar.ts` = data pemilih, `<id>.ts` = pembangun). Pilih lewat `GAYA` di config atau `?gaya=`.
- `src/OfficeScene.tsx`: scene 3D (semua bentuk/bahan lewat kit gaya). `src/App.tsx`: label, HUD, Mission Board.
- `scripts/rekam.mjs`: rekam timelapse jadi MP4.

## Perintah
- `npm run dev` (http://localhost:5173, `?timelapse=1`, `?jam=08.10`), `npm test`, `npm run build`,
  `npm run rekam -- out.mp4`.

## Pembagian kerja (pakai kekuatan masing-masing)
| Agen | Cocok untuk |
|---|---|
| **Claude Code** (berbayar) | Perubahan besar lintas file, desain ulang scene, fitur baru, review akhir, rekam video final |
| **Codex** (gratis) | Satu perubahan kecil: ganti agen/jadwal di `config.ts`, satu bug, satu tes |
| **Antigravity** (gratis) | Coba 2–3 variasi tampilan (warna, ruangan, kamera) dan cek dengan screenshot |

## Aturan
- Setelah mengubah logika, jalankan `npm test`; setelah mengubah tampilan, buka `npm run dev` dan lihat hasilnya.
- Jangan tampilkan nominal uang atau data rahasia di laporan kalau videonya mau dibagikan.
- Jangan menambah teks atau klaim di layar yang tidak diminta.
- Bentuk 3D tetap sederhana (box, kapsul, bola; tanpa model; tekstur hanya dari kanvas) supaya ringan di HP.
