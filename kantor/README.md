# Kantor AI 3D (template gratis)

Kantor isometrik 3D untuk agen AI kamu: tiap agen duduk di mejanya, mengetik saat jam tugas, menulis laporan sore, belajar malam, dan saat santai ngopi, lihat Mission Board, atau ngobrol di sofa. Ada gelembung ringkasan, tanda "!" untuk butir yang menunggu keputusan, meja berkedip untuk yang mendesak, dan timelapse satu hari kerja yang bisa direkam jadi video reels.

Dibuat dengan React + Three.js (bentuk sederhana, tanpa model 3D, jadi ringan di HP). Gratis, lisensi MIT.

Diambil dari halaman "Kantor" di **Imagiive Lapor**, sistem laporan internal Imagiive Group, tempat agen AI kami melapor setiap hari.

## Mulai

Butuh [Node.js](https://nodejs.org) 20+.

```bash
npm install
npm run dev
```

Buka http://localhost:5173.

| Alamat | Isi |
|---|---|
| `/` | Kantor dengan jam sekarang |
| `/?jam=08.10` | Kantor di jam tertentu |
| `/?timelapse=1` | Satu hari kerja dalam 30 detik (pagi, sore, malam) |
| `/?libur=1` | Ikuti akhir pekan sungguhan (default: kantor contoh tetap bekerja) |

## Ubah jadi kantormu

Semua ada di **`src/config.ts`**:

- `KANTOR`: nama dan subjudul di pojok kiri atas.
- `RUANGAN`: tiga ruangan, label, warna lantai dan karpet.
- `AGEN`: nama, tugas, ruangan, warna baju, posisi meja.
- `JADWAL`: jam tugas tiap agen (WIB) dan labelnya ("radar tender…").
- `LAPORAN`: ringkasan, butir menunggu, butir mendesak, dan angka hari ini.
- `BABAK`: tiga babak timelapse.

Tips: biar cepat, buka folder ini di Claude Code dan minta, misalnya, "ganti agennya jadi 4: Admin, Sales, Desainer, Penulis, jadwalnya …".

## Ganti gaya 3D

Ada 16 gaya selain gaya asli. Gaya *menyeluruh* mengubah bentuk dan bahan semua objek (agen, meja, kursi, monitor, dinding, jendela, tanaman, pohon, tanah, Mission Board). Gaya *paduan* menambah dunia di sekitar kantor; posisi agen dan meja tetap ikut `config.ts`.

| Id | Jenis | Isi |
|---|---|---|
| `asli` | bawaan | Bentuk sederhana, warna hangat, paling ringan (default) |
| `clay` | menyeluruh | Plastisin: sudut membulat, bekas jari, pastel |
| `felt` | menyeluruh | Kain flanel/wol: serat, warna lembut, jahitan |
| `voxel` | menyeluruh | Semua objek jadi balok piksel |
| `vinyl` | menyeluruh | Mainan vinyl mengilap, agen chibi kepala besar |
| `diorama` | menyeluruh | Miniatur meja: kayu, kain, rumput, alas kayu, tilt-shift |
| `kayu` | menyeluruh | Balok kayu mainan, agen boneka pasak |
| `stickman` | menyeluruh | Dunia putih bergaris tinta, agen batang tipis |
| `pulau` | paduan | Clay + pulau melayang, laut pastel, awan |
| `toko` | paduan | Lukisan tangan + toko di trotoar, papan nama, lampu jalan |
| `menara` | paduan | Neon + bangunan bertumpuk, tangga zigzag |
| `taman` | paduan | Low-poly + paviliun taman, kolam, pergola |
| `gedung30` | paduan | Voxel + gedung 30 lantai, kantor di lantai cutaway |
| `hologram` | paduan | Blueprint malam: grid cyan, dinding kaca, tepi garis cahaya, Mission Board hologram, partikel data |
| `angkringan` | paduan | Angkringan malam: tikar lesehan, gerobak terpal, tungku arang & ceret, bohlam kuning, motor |
| `pecellele` | paduan | Warung tenda pecel lele: spanduk lukis, meja panjang, bangku plastik, penggorengan, neon, kabel semrawut |
| `bakso` | paduan | Siang depan sekolah: gerobak bakso berkaca, gerobak es, payung pelangi, pohon peneduh, pagar sekolah |

Cara pilih:
- Default: `GAYA` di `src/config.ts`.
- Sekali buka: `/?gaya=clay` (bisa digabung, mis. `/?gaya=menara&timelapse=1`).
- Di layar: tombol **Gaya** di pojok kanan bawah (ganti tanpa muat ulang; pilihan terakhir diingat). Sembunyikan dengan `TAMPIL_PEMILIH_GAYA = false`.
- Rekam: `npm run rekam -- out.mp4 --gaya toko`.

Tiap gaya satu file di `src/gaya/<id>.ts`; daftar namanya di `src/gaya/daftar.ts`. Tekstur dibuat dengan kanvas, tanpa unduhan.

## Sambungkan agen asli

Laporan agen dibaca dari **`src/laporan.json`** (sekarang data contoh). Kuncinya sama dengan `key` di `AGEN`, isinya `ringkasan`, `menunggu`, `mendesak`, dan `angka`. Suruh agenmu (Antigravity, Claude Code, dll.) menulis laporannya ke file ini setiap sore; kantornya langsung berubah. Jangan tampilkan nominal uang atau data rahasia kalau videonya mau dibagikan.

## Rekam jadi video

Butuh Google Chrome dan [ffmpeg](https://ffmpeg.org) (`brew install ffmpeg` di Mac). Biarkan `npm run dev` jalan, lalu di terminal lain:

```bash
npm run rekam -- kantor-ai.mp4
```

Hasilnya MP4 vertikal 1080×1920, 30 fps, 30 detik, direkam frame demi frame (bukan rekam layar), jadi mulus. Opsi: `--w 1920 --h 1080` untuk landscape, `--detik 15`, `--fps 60`. Lokasi Chrome/ffmpeg lain: `CHROME=/path FFMPEG=/path npm run rekam -- out.mp4`.

## Perintah lain

- `npm test`: tes logika jadwal, timelapse, dan agen santai.
- `npm run build`: versi siap unggah di folder `dist/` (bisa ditaruh di Netlify, Vercel, atau GitHub Pages).

## Lisensi

MIT. Bebas dipakai, diubah, dan dibagikan.

## Skill: kantor 3 agen
Unduh `skill/kantor-ai-3-agen.zip`, taruh foldernya di `~/.claude/skills/` (Claude Code) atau minta Codex/Antigravity membaca `SKILL.md`, lalu ketik: "buat kantor AI 3 agen untuk bisnisku".


---
<!-- kredit-maliki -->
**Kredit:** Template oleh Maliki Saputra (@malikisaputra) — https://malikisaputra.biz.id.
**Lisensi Nonkomersial Maliki Studio:** gratis untuk belajar & usaha/organisasi sendiri. Dilarang dijual, dijual ulang, atau dipakai untuk jasa berbayar. Kredit wajib dipertahankan. Lihat `LICENSE`.
