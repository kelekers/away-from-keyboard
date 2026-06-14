"""
Modul Cursor Controller
- Membungkus pyautogui untuk menggerakkan kursor mouse
- Clamping koordinat ke batas layar
- Opsi sensitivitas tambahan (di luar mapping 1:1 dari kalibrasi)
- Dirancang agar mudah di-mock untuk testing (tanpa display/pyautogui)
"""


class CursorController:
    """
    Menggerakkan kursor mouse berdasarkan koordinat layar yang sudah
    dipetakan oleh CalibrationManager.map_to_screen().

    Mapping dari kalibrasi sudah 1:1 (sesuai keputusan desain proyek),
    jadi modul ini hanya melakukan:
      1. Clamping ke batas layar (agar tidak error / kursor "hilang"
         saat fingertip keluar area kalibrasi).
      2. Memanggil pyautogui.moveTo() untuk benar-benar menggerakkan
         kursor.

    `backend` opsional disediakan untuk testing - jika None, modul akan
    mengimport pyautogui secara lazy (saat pertama kali dipakai), supaya
    modul ini tetap bisa di-import di environment tanpa display.
    """

    def __init__(self, screen_width: int, screen_height: int, backend=None):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self._backend = backend
        self._pyautogui = None

        if backend is None:
            # Lazy import - hindari error saat modul di-import tanpa display
            try:
                import pyautogui
                pyautogui.FAILSAFE = False  # kita sudah clamp sendiri
                pyautogui.PAUSE = 0  # tidak ada delay tambahan antar call (penting untuk real-time)
                self._pyautogui = pyautogui
            except Exception as e:
                print(f"[CursorController] Warning: pyautogui tidak tersedia ({e}). "
                      "Cursor tidak akan benar-benar bergerak.")

    def clamp(self, x: float, y: float) -> tuple[int, int]:
        """Clamp koordinat ke dalam batas layar [0, width-1] x [0, height-1]."""
        cx = max(0, min(int(x), self.screen_width - 1))
        cy = max(0, min(int(y), self.screen_height - 1))
        return cx, cy

    def move_to(self, x: float, y: float):
        """
        Gerakkan kursor ke (x, y) dalam koordinat layar. Koordinat akan
        di-clamp otomatis ke batas layar.
        """
        cx, cy = self.clamp(x, y)

        if self._backend is not None:
            self._backend.move_to(cx, cy)
        elif self._pyautogui is not None:
            self._pyautogui.moveTo(cx, cy)
        # jika kedua backend None, no-op (silent) - berguna untuk dev tanpa display

        return cx, cy

    def click(self, button: str = "left"):
        """Lakukan klik mouse pada posisi kursor saat ini."""
        if self._backend is not None:
            self._backend.click(button=button)
        elif self._pyautogui is not None:
            self._pyautogui.click(button=button)


class MockCursorBackend:
    """
    Backend mock untuk testing - mencatat semua pemanggilan move_to/click
    tanpa benar-benar menggerakkan mouse. Berguna untuk unit test di
    environment tanpa display.
    """

    def __init__(self):
        self.positions: list[tuple[int, int]] = []
        self.clicks: list[str] = []

    def move_to(self, x: int, y: int):
        self.positions.append((x, y))

    def click(self, button: str = "left"):
        self.clicks.append(button)

    @property
    def last_position(self):
        return self.positions[-1] if self.positions else None