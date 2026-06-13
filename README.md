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
3. Kalibrasi (4 titik ekstrem layar)
4. Cursor Control + Dynamic Re-scaling
5. Gesture Klik (1 jari -> 2 jari naik = klik kiri)
6. UX & Stabilitas (overlay, pause/resume, error handling)
7. (Opsional) Gesture tambahan: klik kanan, drag, scroll

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