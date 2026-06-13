"""
Modul Calibration Manager
- Mengelola proses kalibrasi 4 titik ekstrem layar (atas, bawah, kiri, kanan)
- Menyimpan & memuat hasil kalibrasi ke/dari file JSON
- Menyediakan fungsi mapping dari posisi fingertip (pixel kamera) ke
  koordinat layar (pixel screen), dengan auto re-scaling berdasarkan
  distance_ratio dari FaceTracker (Sprint 1).

Konsep Kalibrasi:
User menunjukkan 2 jari ke 4 titik ekstrem layar:
  - TOP    : titik paling atas layar
  - BOTTOM : titik paling bawah layar
  - LEFT   : titik paling kiri layar
  - RIGHT  : titik paling kanan layar

Untuk tiap titik, program merekam:
  - posisi fingertip (telunjuk) dalam koordinat kamera (pixel)
  - diameter iris saat itu (untuk referensi jarak)

Dari 4 titik ini terbentuk bounding box di "ruang kamera"
(cam_left, cam_right, cam_top, cam_bottom) yang dipetakan secara linear
ke bounding box layar penuh (0,0) - (screen_width, screen_height).

Auto Re-scaling (lihat Sprint 1 FaceTracker.distance_ratio):
Saat runtime, jika user berada di jarak berbeda dari saat kalibrasi,
bounding box ruang kamera di-scale relatif terhadap titik tengahnya
menggunakan distance_ratio, sebelum dipetakan ke layar. Ini membuat
area kontrol tetap "terasa" sama secara proporsional meski user
maju/mundur.
"""

import json
import os
from dataclasses import dataclass, asdict
from enum import Enum


class CalibrationPoint(Enum):
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


# Urutan kalibrasi yang harus diikuti user
CALIBRATION_ORDER = [
    CalibrationPoint.TOP,
    CalibrationPoint.BOTTOM,
    CalibrationPoint.LEFT,
    CalibrationPoint.RIGHT,
]

# Instruksi yang ditampilkan ke user untuk masing-masing titik
CALIBRATION_INSTRUCTIONS = {
    CalibrationPoint.TOP: "Arahkan 2 jari ke titik PALING ATAS layar, lalu tahan",
    CalibrationPoint.BOTTOM: "Arahkan 2 jari ke titik PALING BAWAH layar, lalu tahan",
    CalibrationPoint.LEFT: "Arahkan 2 jari ke titik PALING KIRI layar, lalu tahan",
    CalibrationPoint.RIGHT: "Arahkan 2 jari ke titik PALING KANAN layar, lalu tahan",
}

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "calibration.json",
)


@dataclass
class CalibrationData:
    # Bounding box di ruang kamera (pixel), hasil dari 4 titik kalibrasi
    cam_left: float
    cam_right: float
    cam_top: float
    cam_bottom: float

    # Resolusi layar saat kalibrasi (pixel)
    screen_width: int
    screen_height: int

    # Diameter iris referensi (pixel) saat kalibrasi - dipakai untuk
    # menghitung distance_ratio di runtime (Sprint 1: FaceTracker)
    reference_iris_diameter_px: float

    # Resolusi frame kamera saat kalibrasi (untuk normalisasi jika
    # resolusi kamera berubah antar sesi)
    frame_width: int
    frame_height: int

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "CalibrationData":
        return CalibrationData(**d)


class CalibrationManager:
    """
    Mengelola flow kalibrasi 4 titik dan mapping fingertip -> koordinat layar.

    Cara pakai (flow runtime):
        cm = CalibrationManager(screen_width, screen_height)
        cm.start()
        # untuk tiap frame selama proses kalibrasi:
        cm.update(fingertip_px, iris_diameter_px, two_finger_gesture_detected)
        # setelah selesai (cm.is_calibrated == True):
        cm.save()

    Cara pakai (flow setelah kalibrasi / load dari file):
        cm = CalibrationManager(screen_width, screen_height)
        cm.load()
        screen_x, screen_y = cm.map_to_screen(fingertip_px, current_iris_diameter_px)
    """

    # Berapa frame berturut-turut gesture "2 jari diam" harus terdeteksi
    # sebelum titik dianggap "dikonfirmasi". Mencegah kalibrasi ter-trigger
    # oleh gerakan sesaat / noise.
    CONFIRM_FRAMES_REQUIRED = 15

    # Toleransi pergerakan fingertip (pixel) selama "menahan" titik.
    # Jika fingertip bergerak lebih dari ini, counter konfirmasi di-reset.
    HOLD_TOLERANCE_PX = 25

    def __init__(self, screen_width: int, screen_height: int,
                 config_path: str = DEFAULT_CONFIG_PATH):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.config_path = config_path

        self.data: CalibrationData | None = None

        # State untuk proses kalibrasi aktif
        self._calibrating = False
        self._current_step_idx = 0
        self._recorded_points: dict[CalibrationPoint, tuple[float, float]] = {}
        self._recorded_iris_diameters: list[float] = []

        # State untuk "hold to confirm"
        self._hold_start_pos: tuple[float, float] | None = None
        self._hold_confirm_count = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def is_calibrated(self) -> bool:
        return self.data is not None

    @property
    def is_calibrating(self) -> bool:
        return self._calibrating

    @property
    def current_step(self) -> CalibrationPoint | None:
        if not self._calibrating:
            return None
        if self._current_step_idx >= len(CALIBRATION_ORDER):
            return None
        return CALIBRATION_ORDER[self._current_step_idx]

    @property
    def current_instruction(self) -> str:
        step = self.current_step
        if step is None:
            return ""
        return CALIBRATION_INSTRUCTIONS[step]

    @property
    def progress(self) -> tuple[int, int]:
        """(langkah_selesai, total_langkah)"""
        return (self._current_step_idx, len(CALIBRATION_ORDER))

    @property
    def hold_progress(self) -> float:
        """Progress 'menahan' titik saat ini, 0.0 - 1.0"""
        return min(1.0, self._hold_confirm_count / self.CONFIRM_FRAMES_REQUIRED)

    # ------------------------------------------------------------------
    # Flow kalibrasi
    # ------------------------------------------------------------------
    def start(self):
        """Mulai proses kalibrasi dari awal."""
        self._calibrating = True
        self._current_step_idx = 0
        self._recorded_points = {}
        self._recorded_iris_diameters = []
        self._hold_start_pos = None
        self._hold_confirm_count = 0

    def cancel(self):
        """Batalkan proses kalibrasi yang sedang berjalan."""
        self._calibrating = False
        self._hold_start_pos = None
        self._hold_confirm_count = 0

    def update(self, fingertip_px: tuple[float, float] | None,
               iris_diameter_px: float | None,
               two_finger_gesture: bool) -> bool:
        """
        Dipanggil setiap frame selama proses kalibrasi berjalan.

        Args:
            fingertip_px: posisi (x, y) ujung jari telunjuk dalam pixel
                kamera, atau None jika tangan tidak terdeteksi.
            iris_diameter_px: diameter iris saat ini (pixel), atau None
                jika wajah tidak terdeteksi.
            two_finger_gesture: True jika user sedang menunjukkan gesture
                2 jari (telunjuk + tengah terangkat) sebagai tanda "ini
                titiknya".

        Returns:
            True jika satu titik baru berhasil dikonfirmasi pada frame ini
            (berguna untuk memicu feedback/sound di UI).
        """
        if not self._calibrating or self.current_step is None:
            return False

        if fingertip_px is None or iris_diameter_px is None or not two_finger_gesture:
            # Reset hold jika syarat tidak terpenuhi
            self._hold_start_pos = None
            self._hold_confirm_count = 0
            return False

        # Cek apakah posisi masih dalam toleransi "menahan"
        if self._hold_start_pos is None:
            self._hold_start_pos = fingertip_px
            self._hold_confirm_count = 1
        else:
            dx = fingertip_px[0] - self._hold_start_pos[0]
            dy = fingertip_px[1] - self._hold_start_pos[1]
            dist = (dx ** 2 + dy ** 2) ** 0.5
            if dist <= self.HOLD_TOLERANCE_PX:
                self._hold_confirm_count += 1
            else:
                # Posisi bergeser terlalu jauh, mulai hitung ulang dari posisi baru
                self._hold_start_pos = fingertip_px
                self._hold_confirm_count = 1

        if self._hold_confirm_count >= self.CONFIRM_FRAMES_REQUIRED:
            # Titik terkonfirmasi! Rata-ratakan posisi selama hold
            confirmed_pos = self._hold_start_pos
            self._recorded_points[self.current_step] = confirmed_pos
            self._recorded_iris_diameters.append(iris_diameter_px)

            # Reset hold state untuk titik berikutnya
            self._hold_start_pos = None
            self._hold_confirm_count = 0
            self._current_step_idx += 1

            if self._current_step_idx >= len(CALIBRATION_ORDER):
                self._finalize_calibration()

            return True

        return False

    def _finalize_calibration(self):
        """Hitung bounding box ruang kamera dari 4 titik yang sudah direkam."""
        top_pos = self._recorded_points[CalibrationPoint.TOP]
        bottom_pos = self._recorded_points[CalibrationPoint.BOTTOM]
        left_pos = self._recorded_points[CalibrationPoint.LEFT]
        right_pos = self._recorded_points[CalibrationPoint.RIGHT]

        cam_top = top_pos[1]
        cam_bottom = bottom_pos[1]
        cam_left = left_pos[0]
        cam_right = right_pos[0]

        # Diameter iris referensi = rata-rata dari semua titik kalibrasi
        ref_iris = sum(self._recorded_iris_diameters) / len(self._recorded_iris_diameters)

        self.data = CalibrationData(
            cam_left=cam_left,
            cam_right=cam_right,
            cam_top=cam_top,
            cam_bottom=cam_bottom,
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            reference_iris_diameter_px=ref_iris,
            frame_width=0,  # diisi oleh caller via set_frame_size sebelum save
            frame_height=0,
        )

        self._calibrating = False

    def set_frame_size(self, frame_width: int, frame_height: int):
        """Set resolusi frame kamera (dipanggil sebelum save())."""
        if self.data is not None:
            self.data.frame_width = frame_width
            self.data.frame_height = frame_height

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: str | None = None):
        if self.data is None:
            raise RuntimeError("Tidak ada data kalibrasi untuk disimpan.")
        path = path or self.config_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.data.to_dict(), f, indent=2)

    def load(self, path: str | None = None) -> bool:
        """
        Muat kalibrasi dari file. Mengembalikan True jika berhasil,
        False jika file tidak ditemukan atau invalid.
        """
        path = path or self.config_path
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r") as f:
                raw = json.load(f)
            self.data = CalibrationData.from_dict(raw)
            return True
        except (json.JSONDecodeError, TypeError, KeyError):
            self.data = None
            return False

    def reset(self):
        """Hapus data kalibrasi yang ada (di memori, belum tentu di file)."""
        self.data = None

    # ------------------------------------------------------------------
    # Mapping fingertip -> koordinat layar
    # ------------------------------------------------------------------
    def map_to_screen(self, fingertip_px: tuple[float, float],
                       current_iris_diameter_px: float | None) -> tuple[float, float]:
        """
        Petakan posisi fingertip (pixel kamera) ke koordinat layar (pixel).

        Jika current_iris_diameter_px diberikan dan valid, bounding box
        ruang kamera akan di-scale relatif terhadap titik tengahnya
        berdasarkan rasio jarak (auto re-scaling), sehingga area kontrol
        efektif menyesuaikan jarak user terhadap layar.

        Hasil koordinat TIDAK di-clamp ke batas layar - caller (cursor
        controller, Sprint 3) bertanggung jawab untuk clamping jika
        diperlukan.
        """
        if self.data is None:
            raise RuntimeError("Belum dikalibrasi. Panggil load() atau lakukan kalibrasi terlebih dahulu.")

        cam_left = self.data.cam_left
        cam_right = self.data.cam_right
        cam_top = self.data.cam_top
        cam_bottom = self.data.cam_bottom

        # --- Auto re-scaling berdasarkan distance_ratio ---
        if current_iris_diameter_px and current_iris_diameter_px > 0:
            ratio = self.data.reference_iris_diameter_px / current_iris_diameter_px
            # ratio > 1 -> user lebih jauh dari kamera dibanding saat
            # kalibrasi -> gerakan tangan secara fisik "lebih besar" perlu
            # dipetakan ke area layar yang sama -> perbesar bounding box
            # ruang kamera (scale up) supaya rentang gerak tangan yang
            # sama tetap menghasilkan rentang kursor yang sama.
            cx = (cam_left + cam_right) / 2.0
            cy = (cam_top + cam_bottom) / 2.0
            half_w = (cam_right - cam_left) / 2.0 * ratio
            half_h = (cam_bottom - cam_top) / 2.0 * ratio

            cam_left = cx - half_w
            cam_right = cx + half_w
            cam_top = cy - half_h
            cam_bottom = cy + half_h

        fx, fy = fingertip_px

        cam_w = cam_right - cam_left
        cam_h = cam_bottom - cam_top

        if cam_w == 0 or cam_h == 0:
            return (0.0, 0.0)

        norm_x = (fx - cam_left) / cam_w
        norm_y = (fy - cam_top) / cam_h

        screen_x = norm_x * self.data.screen_width
        screen_y = norm_y * self.data.screen_height

        return (screen_x, screen_y)