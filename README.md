# AFK - Away From Keyboard

Aplikasi untuk mengontrol kursor & klik laptop hanya menggunakan gerakan tangan
yang ditangkap webcam, tanpa menyentuh mouse/keyboard.

## Sprint 0: Setup & Riset Dasar

Sprint ini berisi proof-of-concept:
- Capture webcam real-time
- Render landmark tangan (MediaPipe Hands) & landmark iris mata (MediaPipe Face Mesh)
- Toggle aktif/nonaktif program via hotkey **Win+A**

### Cara Menjalankan

```bash
cd afk_project
source venv/bin/activate   # (Linux/Mac) atau venv\Scripts\activate (Windows)
python main.py
```

### Kontrol
- **Win+A** : toggle status program AKTIF / NONAKTIF
- **q**     : keluar dari program (saat window video aktif)

### Catatan
- Saat AKTIF, overlay status akan berubah warna hijau. Saat NONAKTIF (default
  ketika program baru dijalankan), warna merah.
- Landmark iris (titik magenta) digunakan untuk Sprint berikutnya: estimasi
  jarak mata-ke-kamera (untuk auto re-scaling kalibrasi).
- Belum ada logic kontrol kursor di sprint ini — fokus hanya verifikasi
  tracking & hotkey berjalan.

### Dependencies
Lihat `requirements.txt`. Sudah diinstall: `opencv-python`, `mediapipe`,
`pyautogui`, `pynput`.

> **Penting:** MediaPipe versi 0.10.35+ menghapus API `mp.solutions` (legacy
> Face Mesh/Hands API) dan menggantinya dengan Tasks API. Proyek ini
> menggunakan `mediapipe==0.10.14` (pinned) karena masih mendukung
> `mp.solutions.face_mesh` & `mp.solutions.hands` yang lebih sederhana untuk
> use case ini. Jangan upgrade mediapipe tanpa migrasi kode ke Tasks API.

### Catatan Platform
- Hotkey `Win+A` via `pynput` (`keyboard.Key.cmd`) berfungsi di Windows. Di
  Linux/Mac, tombol `cmd`/`super` mungkin perlu permission tambahan
  (Accessibility di Mac, atau akses `/dev/input` di Linux). Jika hotkey tidak
  terdeteksi di sistem dev, gunakan tombol alternatif sementara untuk testing.
- Webcam permission harus diizinkan oleh OS.

## Struktur Proyek (akan berkembang di sprint berikutnya)

```
afk_project/
├── main.py              # entry point
├── afk/
│   ├── tracker/         # modul tracking tangan & wajah (Sprint 1+)
│   └── utils/           # helper functions
├── config/               # hasil kalibrasi tersimpan di sini (Sprint 2)
├── requirements.txt
└── README.md
```

## Roadmap Sprint
1. ✅ Setup & Riset Dasar (capture, landmark render, hotkey Win+A)
2. ✅ Hand & Eye Tracking Pipeline (deteksi jari, estimasi jarak via iris)
3. ✅ Kalibrasi (4 titik ekstrem layar)
4. Cursor Control + Dynamic Re-scaling
5. Gesture Klik (1 jari -> 2 jari naik = klik kiri)
6. UX & Stabilitas (overlay, pause/resume, error handling)
7. (Opsional) Gesture tambahan: klik kanan, drag, scroll

## Sprint 2: Kalibrasi

Penambahan dari Sprint 1:

- **`afk/calibration.py`** — modul `CalibrationManager`:
  - Flow kalibrasi 4 titik berurutan: **TOP -> BOTTOM -> LEFT -> RIGHT**.
  - Trigger titik: gesture **2 jari** (telunjuk + tengah terangkat, jari
    lain terlipat) **ditahan diam** selama `CONFIRM_FRAMES_REQUIRED` (15
    frame, ~0.5 detik @30fps) dalam toleransi `HOLD_TOLERANCE_PX` (25px).
    Jika tangan bergeser terlalu jauh, hitungan "hold" reset dan mulai
    lagi dari posisi baru — mencegah kalibrasi ter-trigger oleh gerakan
    tidak sengaja.
  - Setelah 4 titik terkonfirmasi, dihitung bounding box ruang kamera
    (`cam_left`, `cam_right`, `cam_top`, `cam_bottom`) + diameter iris
    referensi (rata-rata dari 4 titik).
  - **Disimpan ke `config/calibration.json`** — otomatis di-load saat
    program start, sehingga user tidak perlu kalibrasi ulang setiap buka
    program (kecuali tekan `c` untuk re-kalibrasi).
  - **`map_to_screen()`** — memetakan posisi fingertip (pixel kamera) ke
    koordinat layar (pixel), dengan **auto re-scaling** berdasarkan rasio
    `reference_iris_diameter_px / current_iris_diameter_px`: jika user
    menjauh, area kontrol di ruang kamera membesar (skala dari titik
    tengah) supaya jangkauan kursor di layar tetap konsisten secara
    proporsional.

- **`main.py`** — terintegrasi:
  - Otomatis load kalibrasi tersimpan saat start.
  - Tekan **`c`** untuk mulai/mengulang kalibrasi kapan saja.
  - Overlay khusus saat kalibrasi: instruksi per langkah, progress
    bar "hold to confirm", indikator gesture 2 jari (hijau = valid,
    merah = belum/invalid).
  - Setelah dikalibrasi, overlay bawah menampilkan **preview** hasil
    mapping fingertip -> koordinat layar (belum menggerakkan kursor asli
    — itu Sprint 3).

### Sudah Diverifikasi (unit test logic, tanpa webcam)
- Flow kalibrasi penuh (4 titik, 60 frame @15 frame/titik) — OK,
  menghasilkan bounding box & referensi iris yang benar.
- Save & load ke/dari `config/calibration.json` — OK.
- `map_to_screen()`: mapping titik tengah & sudut-sudut bounding box ke
  layar — OK.
- Auto re-scaling: simulasi user menjauh (ratio=2) dan mendekat (ratio=0.5)
  — area kontrol membesar/mengecil sesuai ekspektasi — OK.
- Edge case "hold tolerance reset" (tangan bergeser di tengah hold) — OK,
  hitungan reset dan tetap bisa terkonfirmasi setelah stabil kembali.

### Belum diuji (perlu webcam asli di laptopmu)
- Apakah gesture 2 jari (telunjuk+tengah) nyaman & akurat ditahan diam
  selama ~0.5 detik untuk tiap titik kalibrasi.
- Apakah `HOLD_TOLERANCE_PX=25` dan `CONFIRM_FRAMES_REQUIRED=15` terasa pas
  (terlalu sensitif/tidak), perlu tuning berdasarkan FPS aktual & ukuran
  resolusi kamera.
- Akurasi mapping preview di koordinat layar real saat fingertip diarahkan
  ke 4 sudut layar setelah kalibrasi.
- Perilaku auto re-scaling saat user benar-benar maju/mundur dari layar.

### Catatan
- `config/calibration.json` di-gitignore-kan sebaiknya (data personal per
  user/device) — lihat `.gitignore` yang ditambahkan di sprint ini.

## Sprint 1: Hand & Eye Tracking Pipeline

Penambahan dari Sprint 0:

- **`afk/tracker/hand_tracker.py`** — modul `HandTracker`:
  - Deteksi 1 tangan (bebas kiri/kanan).
  - `count_raised_fingers()` — deteksi status tiap jari (telunjuk, tengah,
    manis, kelingking via perbandingan tip vs pip; jempol via jarak
    horizontal terhadap wrist agar robust untuk tangan kiri/kanan).
  - `get_index_fingertip()` / `get_middle_fingertip()` — posisi ujung jari
    dalam pixel, untuk kontrol kursor (Sprint 3) dan gesture klik (Sprint 4).

- **`afk/tracker/face_tracker.py`** — modul `FaceTracker`:
  - Hitung **diameter iris** (rata-rata 4 pengukuran: horizontal & vertikal,
    mata kiri & kanan) dalam pixel.
  - `distance_ratio()` — rasio diameter iris saat ini terhadap diameter
    referensi (diset saat kalibrasi, Sprint 2). Ratio > 1 = user lebih
    jauh dari saat kalibrasi, ratio < 1 = lebih dekat. Ini akan dipakai
    untuk auto re-scaling area kontrol kursor (Sprint 3).

- **`afk/utils/smoothing.py`** — `EMASmoother`, exponential moving average
  untuk posisi fingertip & diameter iris (mengurangi jitter).

- **`main.py`** — terintegrasi dengan modul-modul di atas. Overlay sekarang
  menampilkan status tiap jari, total jari terangkat, dan diameter iris
  (px) sebagai proxy jarak mata-kamera.

### Sudah Diverifikasi (unit test logic, tanpa webcam)
- `EMASmoother`: smoothing scalar & tuple, reset behavior — OK.
- `count_raised_fingers()`: skenario 1 jari & 2 jari terangkat — OK.
- `iris_diameter_px()` & `distance_ratio()`: perhitungan geometris &
  rasio jarak — OK.

### Belum diuji (perlu webcam asli di laptopmu)
- Akurasi deteksi jari real-time (terutama jempol & kondisi cahaya
  bervariasi).
- Stabilitas diameter iris saat kepala bergerak/miring.
- Tuning `alpha` pada EMASmoother (saat ini: fingertip=0.5, iris=0.3).