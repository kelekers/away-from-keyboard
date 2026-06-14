"""
Modul Click Gesture Detector

Konsep gesture klik (sesuai desain proyek):
  1. User menggerakkan kursor dengan gesture 1 jari (telunjuk).
  2. Saat posisi kursor sudah pas, user mengangkat jari tengah juga
     (sehingga jadi gesture 2 jari).
  3. Jari tengah kemudian "dinaikkan" (gerakan CEPAT ke atas) -> ini
     men-trigger klik kiri.

Implementasi (velocity-based):
  - Selama gesture 2 jari aktif, modul ini memantau posisi Y (pixel)
    dari ujung jari tengah dari frame ke frame.
  - Dihitung "velocity" = (posisi_y_frame_sebelumnya - posisi_y_sekarang)
    per frame. Velocity positif berarti bergerak ke atas (origin frame
    di kiri-atas, Y mengecil ke atas).
  - Klik ter-trigger jika velocity >= UP_VELOCITY_THRESHOLD_PX_PER_FRAME
    pada satu frame - ini secara natural membedakan:
      * Gerakan CEPAT (flick) -> velocity tinggi dalam 1 frame -> trigger
      * Drift LAMBAT saat reposisi -> velocity rendah per frame -> TIDAK
        trigger meskipun total perpindahan besar.
  - Setelah klik ter-trigger, ada `cooldown` (debounce) sebelum klik
    berikutnya bisa terjadi.

Catatan desain:
  - Velocity dihitung dari posisi MENTAH (bukan smoothed) jari tengah,
    karena smoothing (EMA) akan meredam velocity dan membuat flick cepat
    sulit terdeteksi. Caller (main.py) harus memberikan posisi mentah
    untuk modul ini, terpisah dari posisi smoothed yang dipakai untuk
    kontrol kursor.
  - Jika gesture 2 jari hilang (user menurunkan salah satu jari), state
    posisi sebelumnya di-reset - mencegah lompatan velocity palsu saat
    gesture baru dimulai.
"""


class ClickGestureDetector:
    """
    Mendeteksi gesture klik: gerakan CEPAT ke atas dari jari tengah
    (berdasarkan velocity per-frame) saat gesture 2 jari (telunjuk +
    tengah) aktif.

    Cara pakai (dipanggil setiap frame):
        detector = ClickGestureDetector()
        clicked = detector.update(two_finger_gesture, middle_fingertip_y_px)
        if clicked:
            cursor_controller.click("left")
    """

    # Ambang velocity (pixel per frame) ke ATAS untuk men-trigger klik.
    # Nilai ini perlu di-tuning sesuai FPS aktual & resolusi kamera.
    # Pada ~30fps, 18px/frame setara ~540px/detik - gerakan "menyentil"
    # cepat, bukan reposisi normal.
    UP_VELOCITY_THRESHOLD_PX_PER_FRAME = 18

    # Setelah klik ter-trigger, berapa frame harus menunggu sebelum klik
    # berikutnya bisa terjadi (debounce / cooldown).
    COOLDOWN_FRAMES = 15

    def __init__(self):
        self._prev_y: float | None = None
        self._cooldown_remaining = 0
        self._last_velocity: float = 0.0

    def reset(self):
        """Reset posisi sebelumnya - dipanggil saat gesture 2 jari hilang."""
        self._prev_y = None
        self._last_velocity = 0.0
        # cooldown TIDAK direset di sini secara sengaja - cooldown tetap
        # berjalan meski gesture hilang, supaya user tidak bisa "spam"
        # klik dengan cepat melepas & mengulang gesture.

    def update(self, two_finger_gesture: bool, middle_fingertip_y_px: float | None) -> bool:
        """
        Dipanggil setiap frame.

        Args:
            two_finger_gesture: True jika gesture 2 jari (telunjuk +
                tengah, jari lain terlipat) terdeteksi pada frame ini.
            middle_fingertip_y_px: posisi Y (pixel, MENTAH/tidak
                di-smoothing) ujung jari tengah, atau None jika tangan
                tidak terdeteksi.

        Returns:
            True jika klik ter-trigger pada frame ini.
        """
        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1

        if not two_finger_gesture or middle_fingertip_y_px is None:
            self.reset()
            return False

        if self._prev_y is None:
            # Frame pertama gesture 2 jari - belum ada velocity untuk dihitung
            self._prev_y = middle_fingertip_y_px
            self._last_velocity = 0.0
            return False

        # Velocity positif = bergerak ke atas (Y mengecil)
        velocity = self._prev_y - middle_fingertip_y_px
        self._last_velocity = velocity
        self._prev_y = middle_fingertip_y_px

        if velocity >= self.UP_VELOCITY_THRESHOLD_PX_PER_FRAME:
            if self._cooldown_remaining == 0:
                self._cooldown_remaining = self.COOLDOWN_FRAMES
                return True
            return False

        return False

    @property
    def is_in_cooldown(self) -> bool:
        return self._cooldown_remaining > 0

    @property
    def last_velocity(self) -> float:
        """Velocity terakhir (pixel/frame, positif = ke atas) - untuk debug/overlay."""
        return self._last_velocity