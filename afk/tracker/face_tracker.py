"""
Modul Face Tracker
- Membungkus MediaPipe Face Mesh (dengan refine_landmarks=True untuk iris)
- Menghitung diameter iris dalam pixel
- Mengestimasi jarak relatif mata-ke-kamera berdasarkan diameter iris

Konsep:
Diameter iris manusia relatif konstan (~11.7 mm rata-rata dewasa). Karena
proyeksi kamera bersifat perspektif, semakin dekat mata ke kamera, semakin
besar diameter iris dalam pixel, dan sebaliknya.

Hubungan: distance_mm = (IRIS_DIAMETER_MM * FOCAL_LENGTH_PX) / iris_diameter_px

Untuk Sprint 1, kita belum perlu nilai distance dalam mm yang presisi —
yang penting adalah *rasio* terhadap jarak referensi saat kalibrasi
(Sprint 2). Maka modul ini menyediakan:
  1. iris_diameter_px(): ukuran iris dalam pixel (raw measurement)
  2. distance_ratio(): rasio iris_diameter_px saat ini terhadap referensi
     -> ratio > 1 berarti user lebih dekat ke kamera dibanding saat
        kalibrasi, ratio < 1 berarti lebih jauh.

Referensi iris diameter (mm) tetap disediakan sebagai konstanta jika
nanti diperlukan estimasi jarak absolut (misal dengan kalibrasi focal
length kamera).
"""

import math
import mediapipe as mp


# Rata-rata diameter iris manusia dewasa (mm) - nilai umum yang dipakai
# di berbagai riset computer vision untuk estimasi jarak.
IRIS_DIAMETER_MM = 11.7

# Landmark index iris (tersedia hanya jika refine_landmarks=True)
LEFT_IRIS = [468, 469, 470, 471, 472]   # 468 = center, 469-472 = tepi
RIGHT_IRIS = [473, 474, 475, 476, 477]  # 473 = center, 474-477 = tepi

# Index tepi horizontal & vertikal iris (untuk hitung diameter)
LEFT_IRIS_HORIZONTAL = (469, 471)
LEFT_IRIS_VERTICAL = (470, 472)
RIGHT_IRIS_HORIZONTAL = (474, 476)
RIGHT_IRIS_VERTICAL = (475, 477)


class FaceTracker:
    def __init__(self, min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5):
        self._mp_face_mesh = mp.solutions.face_mesh
        self._face_mesh = self._mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        # Referensi diameter iris (pixel) saat kalibrasi. Diset oleh
        # CalibrationManager pada Sprint 2 lewat set_reference_iris_diameter().
        self._reference_iris_diameter_px = None

    def process(self, rgb_frame):
        """
        Proses frame RGB dan kembalikan landmark wajah pertama, atau None
        jika tidak ada wajah terdeteksi.
        """
        results = self._face_mesh.process(rgb_frame)
        if results.multi_face_landmarks:
            return results.multi_face_landmarks[0]
        return None

    @staticmethod
    def _euclidean_px(landmarks, idx_a, idx_b, frame_width, frame_height):
        a = landmarks[idx_a]
        b = landmarks[idx_b]
        ax, ay = a.x * frame_width, a.y * frame_height
        bx, by = b.x * frame_width, b.y * frame_height
        return math.hypot(bx - ax, by - ay)

    def iris_diameter_px(self, face_landmarks, frame_width: int, frame_height: int) -> float:
        """
        Hitung rata-rata diameter iris (kiri & kanan, horizontal & vertikal)
        dalam pixel. Mengembalikan rata-rata dari 4 pengukuran untuk hasil
        yang lebih stabil.
        """
        landmarks = face_landmarks.landmark

        left_h = self._euclidean_px(landmarks, *LEFT_IRIS_HORIZONTAL, frame_width, frame_height)
        left_v = self._euclidean_px(landmarks, *LEFT_IRIS_VERTICAL, frame_width, frame_height)
        right_h = self._euclidean_px(landmarks, *RIGHT_IRIS_HORIZONTAL, frame_width, frame_height)
        right_v = self._euclidean_px(landmarks, *RIGHT_IRIS_VERTICAL, frame_width, frame_height)

        return (left_h + left_v + right_h + right_v) / 4.0

    def set_reference_iris_diameter(self, diameter_px: float):
        """
        Set diameter iris referensi (saat kalibrasi). Dipanggil oleh
        CalibrationManager pada Sprint 2.
        """
        self._reference_iris_diameter_px = diameter_px

    def distance_ratio(self, current_diameter_px: float) -> float:
        """
        Hitung rasio jarak saat ini terhadap jarak referensi kalibrasi.

        ratio = reference_diameter_px / current_diameter_px

        - ratio > 1 -> user sekarang LEBIH JAUH dari kamera dibanding saat
          kalibrasi (iris tampak lebih kecil sekarang).
        - ratio < 1 -> user sekarang LEBIH DEKAT.
        - ratio == 1 -> jarak sama seperti saat kalibrasi.

        Rasio ini akan dikalikan ke mapping kalibrasi (Sprint 3) untuk
        auto re-scaling area kontrol kursor.

        Mengembalikan None jika belum ada referensi (belum kalibrasi) atau
        current_diameter_px tidak valid.
        """
        if self._reference_iris_diameter_px is None:
            return None
        if current_diameter_px <= 0:
            return None
        return self._reference_iris_diameter_px / current_diameter_px

    @staticmethod
    def get_iris_landmark_px(face_landmarks, landmark_idx: int, frame_width: int, frame_height: int):
        """Konversi landmark iris (normalized) ke koordinat pixel."""
        lm = face_landmarks.landmark[landmark_idx]
        return int(lm.x * frame_width), int(lm.y * frame_height)

    def close(self):
        self._face_mesh.close()