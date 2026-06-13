"""
Modul Hand Tracker
- Membungkus MediaPipe Hands
- Mendeteksi 1 tangan (bebas kiri/kanan)
- Menghitung jumlah jari yang terangkat (finger count)
- Mengembalikan posisi ujung jari (fingertip), khususnya jari telunjuk
  (untuk kontrol kursor) dan jari tengah (untuk gesture klik)
"""

import mediapipe as mp


# Index landmark MediaPipe Hands (21 titik per tangan)
# Referensi: https://developers.google.com/mediapipe/solutions/vision/hand_landmarker
WRIST = 0

THUMB_TIP = 4
THUMB_IP = 3

INDEX_TIP = 8
INDEX_PIP = 6

MIDDLE_TIP = 12
MIDDLE_PIP = 10

RING_TIP = 16
RING_PIP = 14

PINKY_TIP = 20
PINKY_PIP = 18

# Pasangan (tip, pip) untuk 4 jari selain jempol -> jari "terangkat" jika
# tip.y < pip.y (lebih tinggi di frame, ingat origin (0,0) di kiri atas)
FINGER_TIP_PIP_PAIRS = {
    "index": (INDEX_TIP, INDEX_PIP),
    "middle": (MIDDLE_TIP, MIDDLE_PIP),
    "ring": (RING_TIP, RING_PIP),
    "pinky": (PINKY_TIP, PINKY_PIP),
}


class HandTracker:
    def __init__(self, max_num_hands: int = 1,
                 min_detection_confidence: float = 0.6,
                 min_tracking_confidence: float = 0.6):
        self._mp_hands = mp.solutions.hands
        self._hands = self._mp_hands.Hands(
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def process(self, rgb_frame):
        """
        Proses frame RGB dan kembalikan hasil deteksi tangan mentah dari
        MediaPipe (multi_hand_landmarks), atau None jika tidak ada tangan.
        """
        results = self._hands.process(rgb_frame)
        if results.multi_hand_landmarks:
            return results.multi_hand_landmarks[0]  # hanya 1 tangan
        return None

    @staticmethod
    def count_raised_fingers(hand_landmarks) -> dict:
        """
        Hitung status tiap jari (terangkat / tidak) berdasarkan landmark.

        Mengembalikan dict:
            {
                "index": bool,
                "middle": bool,
                "ring": bool,
                "pinky": bool,
                "thumb": bool,
                "count": int  # total jari terangkat
            }

        Catatan:
        - Jari selain jempol: dianggap "terangkat" jika ujung jari (tip)
          lebih tinggi (y lebih kecil) dibanding sendi tengah (pip).
        - Jempol: dicek secara horizontal relatif terhadap pangkal jempol
          (THUMB_IP), karena gerakan jempol dominan ke samping, bukan
          vertikal. Ini lebih robust untuk berbagai orientasi tangan.
        """
        landmarks = hand_landmarks.landmark
        status = {}

        for name, (tip_idx, pip_idx) in FINGER_TIP_PIP_PAIRS.items():
            tip_y = landmarks[tip_idx].y
            pip_y = landmarks[pip_idx].y
            status[name] = tip_y < pip_y  # tip lebih tinggi dari pip

        # Jempol: cek jarak horizontal tip vs ip relatif terhadap wrist
        thumb_tip = landmarks[THUMB_TIP]
        thumb_ip = landmarks[THUMB_IP]
        wrist = landmarks[WRIST]

        # Jika tangan kanan menghadap kamera (sudah di-flip di main.py),
        # jempol terangkat -> thumb_tip.x lebih jauh dari wrist.x
        # dibanding thumb_ip.x. Gunakan perbandingan jarak absolut agar
        # bekerja untuk tangan kiri/kanan.
        dist_tip = abs(thumb_tip.x - wrist.x)
        dist_ip = abs(thumb_ip.x - wrist.x)
        status["thumb"] = dist_tip > dist_ip

        status["count"] = sum(1 for k in ["index", "middle", "ring", "pinky", "thumb"] if status[k])
        return status

    @staticmethod
    def get_landmark_px(hand_landmarks, landmark_idx: int, frame_width: int, frame_height: int):
        """Konversi landmark (normalized 0-1) ke koordinat pixel (x, y)."""
        lm = hand_landmarks.landmark[landmark_idx]
        return int(lm.x * frame_width), int(lm.y * frame_height)

    @staticmethod
    def get_index_fingertip(hand_landmarks, frame_width: int, frame_height: int):
        """Posisi ujung jari telunjuk dalam pixel - dipakai untuk kontrol kursor."""
        return HandTracker.get_landmark_px(hand_landmarks, INDEX_TIP, frame_width, frame_height)

    @staticmethod
    def get_middle_fingertip(hand_landmarks, frame_width: int, frame_height: int):
        """Posisi ujung jari tengah dalam pixel - dipakai untuk gesture klik (2 jari)."""
        return HandTracker.get_landmark_px(hand_landmarks, MIDDLE_TIP, frame_width, frame_height)

    def close(self):
        self._hands.close()