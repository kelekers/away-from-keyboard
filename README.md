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
4. ✅ Cursor Control + Dynamic Re-scaling
5. ✅ Gesture Klik (1 jari -> 2 jari naik = klik kiri)
6. UX & Stabilitas (overlay, pause/resume, error handling)
7. (Opsional) Gesture tambahan: klik kanan, drag, scroll

## Sprint 4: Gesture Klik

Penambahan dari Sprint 3:

- **`afk/click_gesture.py`** — modul `ClickGestureDetector`:
  - **Velocity-based detection**: setiap frame saat gesture 2 jari
    (telunjuk + tengah) aktif, dihitung `velocity = prev_y - current_y`
    dari posisi Y **mentah** (tidak smoothed) jari tengah. Velocity
    positif = bergerak ke atas.
  - Klik ter-trigger jika `velocity >= UP_VELOCITY_THRESHOLD_PX_PER_FRAME`
    (default **18 px/frame**, ~540px/detik @30fps) — ini secara natural
    membedakan **sentilan cepat** (trigger) dari **drift lambat** saat
    reposisi tangan (tidak trigger), tanpa perlu jendela waktu/baseline
    yang rumit.
  - **Cooldown 15 frame** (~0.5 detik @30fps) setelah klik ter-trigger,
    mencegah klik berulang dari satu gesture yang sama.
  - `reset()` dipanggil saat gesture 2 jari hilang — mencegah lompatan
    velocity palsu saat gesture dimulai kembali dari posisi berbeda.
    Cooldown TIDAK direset agar user tidak bisa "spam" klik dengan
    melepas-pasang gesture cepat.

- **`main.py`** — terintegrasi:
  - Posisi Y mentah jari tengah (`raw_middle_y`, bukan hasil EMA)
    diteruskan ke `ClickGestureDetector` — smoothing akan meredam
    velocity dan membuat sentilan cepat sulit terdeteksi.
  - Klik hanya diproses jika `state.active == True` (toggle Win+A).
  - Saat klik ter-trigger: kursor di-`clamp()` & di-`move_to()` ke
    posisi mapping terakhir (dari jari telunjuk) **sebelum** memanggil
    `cursor_controller.click("left")` — memastikan klik terjadi tepat
    di posisi yang ditunjuk, bukan di posisi jari tengah.
  - Overlay menampilkan indikator visual besar "KLIK!" saat trigger
    terjadi.

### Sudah Diverifikasi (unit test logic, tanpa webcam)
- Drift lambat (5px/frame) selama 20 frame -> **TIDAK** trigger klik.
- Sentilan cepat (25px dalam 1 frame, velocity=25 >= 18) -> **trigger**.
- Cooldown: sentilan kedua langsung setelah klik pertama -> **tidak**
  trigger; setelah 15 frame cooldown selesai, sentilan berikutnya
  -> trigger lagi.
- Gerakan ke BAWAH (velocity negatif) -> tidak trigger.
- Gesture 2 jari hilang lalu muncul lagi di posisi jauh -> tidak
  menghasilkan velocity palsu (prev_y di-reset).
- Integration test penuh: 1 jari gerak kursor ke (960,540) -> ganti ke
  2 jari (baseline) -> sentil ke atas -> `click("left")` terpanggil di
  posisi (960,540) yang benar.
- Klik ditekan saat `state.active == False` -> tidak ada klik
  ter-trigger sama sekali.

### Belum diuji (perlu webcam asli di laptopmu)
- **Tuning `UP_VELOCITY_THRESHOLD_PX_PER_FRAME=18`** — ini sangat
  bergantung pada FPS aktual webcam & resolusi. Jika terlalu sensitif
  (klik tidak sengaja saat reposisi cepat) turunkan threshold; jika
  sulit ter-trigger, naikkan atau perbesar threshold velocity.
- **Tuning `COOLDOWN_FRAMES=15`** — apakah 0.5 detik @30fps terasa pas
  untuk klik berurutan (misal double-click manual).
- Apakah gerakan "menyentil jari tengah ke atas" terasa natural/nyaman
  dilakukan berulang kali.
- Interaksi antara mode 1 jari (gerak kursor) dan 2 jari (klik) — pastikan
  transisi tidak menyebabkan kursor "melompat" tiba-tiba saat jari tengah
  diangkat (karena mapping tetap dari jari telunjuk, seharusnya aman, tapi
  perlu verifikasi visual).

### Catatan untuk Sprint 5 (UX & Stabilitas)
- Saat ini overlay sudah menampilkan banyak info debug. Sprint 5 akan
  mempertimbangkan mode "minimal overlay" untuk penggunaan sehari-hari,
  plus gesture pause/resume dan error handling (tangan/wajah hilang dari
  frame, dll).

## Sprint 3: Cursor Control + Dynamic Re-scaling

Penambahan dari Sprint 2:

- **`afk/cursor_controller.py`** — modul `CursorController`:
  - Membungkus `pyautogui.moveTo()` / `pyautogui.click()`.
  - `clamp()` — koordinat hasil mapping di-clamp ke batas layar
    `[0, width-1] x [0, height-1]`, mencegah error/kursor "hilang" saat
    fingertip keluar area kalibrasi.
  - `pyautogui.FAILSAFE = False` (clamping sudah ditangani sendiri) dan
    `pyautogui.PAUSE = 0` (tidak ada delay tambahan antar call, penting
    untuk real-time).
  - Mendukung `backend` opsional (lazy import pyautogui) supaya modul
    tetap bisa di-import & di-test di environment tanpa display.
  - **`MockCursorBackend`** — backend tiruan untuk unit test (mencatat
    posisi & klik tanpa benar-benar menggerakkan mouse).

- **`main.py`** — terintegrasi penuh:
  - Definisi 2 gesture berdasarkan `finger_status`:
    - **1 jari** (hanya telunjuk terangkat) -> mode **gerak kursor**.
    - **2 jari** (telunjuk + tengah) -> dicadangkan untuk **kalibrasi**
      (Sprint 2) dan **klik** (Sprint 4).
  - Kursor mouse asli digerakkan via `cursor_controller.move_to()` HANYA
    jika: `state.active == True` (toggle Win+A) **DAN** sudah dikalibrasi
    **DAN** gesture 1 jari terdeteksi.
  - Mapping tetap memakai `CalibrationManager.map_to_screen()` dari
    Sprint 2 (1:1 + auto re-scaling berdasarkan jarak iris).
  - Overlay menampilkan status "Kontrol kursor: AKTIF/nonaktif" secara
    real-time.

### Sudah Diverifikasi (unit test logic, tanpa webcam)
- `CursorController.clamp()`: posisi normal, negatif, dan melebihi batas
  layar — semua diclamp dengan benar.
- `MockCursorBackend`: mencatat `move_to`/`click` dengan benar.
- Integrasi gating logic kontrol kursor (5 skenario):
  1. `active=False` + 1 jari -> kursor TIDAK bergerak.
  2. `active=True` + 2 jari -> kursor TIDAK bergerak (gesture dicadangkan).
  3. `active=True` + 1 jari -> kursor bergerak ke posisi mapping yang benar.
  4. Fingertip di sudut kalibrasi (top-left) -> mapping ~(0,0), kursor
     bergerak ke sana.
  5. Fingertip di luar area kalibrasi -> mapping bernilai negatif, namun
     `CursorController` berhasil clamp ke (0,0).

### Belum diuji (perlu webcam + display asli di laptopmu)
- Responsivitas & smoothness gerakan kursor real-time (apakah `alpha=0.5`
  pada `index_tip_smoother` sudah pas — terlalu lag atau masih jitter).
- Transisi antar gesture 1 jari <-> 2 jari: apakah berpindah mode terasa
  natural atau ada "flicker" saat MediaPipe salah deteksi jari sesaat.
- Perilaku `pyautogui.FAILSAFE = False` — pastikan tidak ada efek samping
  saat kursor mendekati pojok layar (biasanya FAILSAFE memicu exception
  jika kursor ke pojok kiri-atas (0,0), kita matikan ini secara sengaja).
- Cek apakah `pyautogui.size()` mengembalikan resolusi yang benar di
  setup multi-monitor (mungkin perlu penyesuaian jika user punya >1
  monitor).

### Catatan untuk Sprint 4 (Gesture Klik)
- Mode "2 jari" sudah disiapkan namun belum dipakai untuk klik. Sprint 4
  akan menambahkan deteksi gerakan **naik** dari posisi 2 jari (perubahan
  posisi Y dalam beberapa frame) sebagai trigger klik kiri, dengan
  cooldown/debounce untuk mencegah klik berulang tidak sengaja.

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