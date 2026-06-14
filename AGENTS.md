INI ADALAH RIWAYATKU DENGAN CLAUDE, AKU MAU KAMU MELANJUTKAN PROJEK KAMI.

AKU:
Aku mau membuat projek bernama AFK di mana ini literally away from keyboard dan mouse. Aplikasi/program ini dapat mentrack gerakan tangan untuk menggerakkan laptop tanpa memegang mouse maupun keyboard. 

Pertama tama program ini perlu kalibrasi yaitu track mata lalu user memberikan tanda dengan dua jari untuk memberi tahu program layar paling bawah, paling kanan, kiri dan atas dari layar saat jarak mata user segitu (nanti program saat berjalan juga track mata untuk menentukan jarak user dengan layar). Adapun untuk kontrolnya 1 jari menggerakan kursor dan dua jari naik berarti klik.

Dari penjelasam proyek ini apakah kamu sudah paham, atau adakah pertanyaan maupun saran pengembangan darimu dulu? di next chat kita mulai bahas arsitekturnya lalu kita bangun programnya

CLAUDE:
Paham konsepnya. Ini ringkasan pemahaman saya plus beberapa pertanyaan/saran sebelum kita lanjut ke arsitektur:

**Pemahaman saya:**
- Tracking mata untuk estimasi jarak/posisi kepala terhadap layar (semacam head-pose/gaze distance estimation).
- Kalibrasi: user menunjukkan 4 titik ekstrem layar (atas/bawah/kiri/kanan) dengan gesture dua jari, pada jarak mata tertentu — ini membentuk mapping antara posisi tangan di ruang kamera ke koordinat layar.
- Runtime: 1 jari = gerakkan kursor, 2 jari "naik" (gesture vertikal) = klik.

**Pertanyaan/hal yang perlu diperjelas:**

1. **Re-kalibrasi saat jarak berubah** — kalau user maju/mundur dari laptop setelah kalibrasi, apakah mapping kalibrasi otomatis di-scale berdasarkan jarak mata-ke-kamera yang baru (interpolasi), atau user harus kalibrasi ulang tiap kali jarak signifikan berubah?

2. **Definisi gesture "2 jari naik untuk klik"** — apakah ini gerakan dua jari naik bersamaan secara cepat (seperti tap di udara), atau menahan dua jari lalu gerak naik perlahan? Perlu didefinisikan threshold kecepatan/jarak agar tidak ke-trigger saat gerakan biasa (gesture ini rawan false-positive).

3. **Tangan mana yang dipakai** — kiri, kanan, atau bebas? Apakah perlu deteksi tangan dominan saat kalibrasi?

4. **Klik kiri vs kanan vs drag** — apakah hanya perlu klik kiri (klik kanan & drag belum dipikirkan dulu), atau perlu dipetakan juga ke gesture lain nantinya?

5. **Platform & library** — target OS apa (Windows/Mac/Linux)? Saya asumsikan akan pakai Python + OpenCV + MediaPipe (Hands + Face Mesh) untuk tracking, dan pyautogui/sejenisnya untuk kontrol mouse. Apakah ini sesuai ekspektasi?

6. **Smoothing/jitter** — gerakan tangan manusia tidak stabil; perlu strategi smoothing (misal exponential moving average) supaya kursor tidak "gemetar". Ini akan jadi bagian penting di arsitektur.

7. **Dead zone & sensitivitas** — apakah skala gerakan tangan ke layar linear 1:1 berdasarkan kalibrasi, atau perlu faktor sensitivitas yang bisa disesuaikan user?

**Saran tambahan:**
- Tambahkan indikator visual (overlay kecil) saat program berjalan untuk menunjukkan status tracking (terdeteksi/tidak, mode kalibrasi/runtime).
- Pertimbangkan gesture "pause/resume" tracking (misal kepalkan tangan) supaya user bisa istirahat tanpa kursor random bergerak.
- Simpan hasil kalibrasi ke file config supaya tidak perlu kalibrasi ulang setiap buka program (kecuali user reset).

Kalau poin-poin di atas sudah cukup jelas arahnya, di chat berikutnya kita bisa langsung masuk ke desain arsitektur (modul-modul: capture, face/hand tracking, calibration manager, gesture recognizer, cursor controller, dll).

AKU:
1. auto rekalibrasi berdasarkan jarak atau ukuran mata, atau ada cara lain yang lebih akurat?
2. Jadi kan menggerakkan kursor dengan 1 jari lalu kalau jari sudah di tempat yang ingin diklik jari satunya tinggal dinaikkan lagi sehingga mentrigger klik
3. Bebas
4. iya klik kiri dulu yang utama, kalau kamu ada saran gestur lain akan lebih bagus
5. iya benar
6. iya, asalkan tetap cepat ya
7. 1:1

saranmu bagus, aku mau menambahkan saran untuk aktivasi programnya klik windows+a. Sekarang buatkan rencana sprintnya dulu, lalu kita akan iterasi satu satu.

CLAUDE:
**Soal #1 - rekomendasi:** Pakai **iris diameter ratio** (MediaPipe Face Mesh punya landmark iris). Diameter iris manusia relatif konstan (~11.7mm), jadi rasio ukuran iris di pixel terhadap diameter asli bisa dipakai untuk estimasi jarak mata-ke-kamera secara konsisten — lebih akurat dan stabil dibanding "ukuran mata" (eye aspect ratio) yang berubah-ubah karena kedipan/ekspresi. Jarak ini lalu dipakai untuk scaling mapping kalibrasi secara real-time (interpolasi linear terhadap jarak referensi saat kalibrasi).

---

# Rencana Sprint — Proyek AFK

### Sprint 0: Setup & Riset Dasar
- Setup environment Python (OpenCV, MediaPipe, pyautogui/pynput, keyboard listener untuk hotkey).
- Buktikan capture webcam real-time + render landmark wajah & tangan (proof of concept, belum ada logic).
- Implementasi hotkey global **Win+A** untuk toggle aktif/nonaktif program (tray icon/console indicator).

### Sprint 1: Hand & Eye Tracking Pipeline
- Modul `tracker`: deteksi 1 tangan (bebas kiri/kanan) + hitung jumlah jari terangkat.
- Modul `face_tracker`: ekstrak landmark iris dari Face Mesh, hitung iris diameter (pixel) → estimasi jarak mata-kamera.
- Smoothing dasar (EMA) untuk posisi jari & jarak mata.

### Sprint 2: Kalibrasi
- Flow kalibrasi: user tunjuk 2 jari ke 4 titik ekstrem layar (atas/bawah/kiri/kanan), program rekam posisi jari (x,y) + jarak mata saat itu.
- Hitung mapping (homography/linear transform) dari ruang kamera → koordinat layar, dengan jarak referensi.
- Simpan hasil kalibrasi ke file config (JSON) — load otomatis saat program start, opsi reset.

### Sprint 3: Cursor Control + Dynamic Re-scaling
- Mode runtime: 1 jari terdeteksi → gerakkan kursor (mapping 1:1, hasil kalibrasi).
- Implementasi auto re-scaling mapping berdasarkan perubahan jarak mata (rasio iris) terhadap jarak referensi kalibrasi.
- Tuning smoothing agar responsif (latency rendah) tapi tidak jitter.

### Sprint 4: Gesture Klik
- Deteksi gesture: 1 jari → 2 jari naik (cepat) = klik kiri.
- Threshold kecepatan/jarak gesture untuk hindari false positive.
- Tambahkan debounce (cooldown) antar klik.

### Sprint 5: UX & Stabilitas
- Overlay indikator status (aktif/nonaktif, mode kalibrasi/runtime, tangan terdeteksi).
- Gesture pause/resume (misal kepalan tangan) — opsional, dibahas saat sprint ini.
- Error handling: tangan/wajah hilang dari frame, multi-hand terdeteksi, dll.

### Sprint 6 (opsional/lanjutan): Gesture Tambahan
- Klik kanan, drag, scroll — eksplorasi gesture lain (misal 3 jari = klik kanan, jari menutup-lalu-gerak = drag).
- Sensitivitas adjustable (meski default 1:1).

KITA SUDAH SAMPAI SPRINT 2 DAN TERNYATA CLAUDE KU HABIS JADI MARI KITA LANJUTKAN!