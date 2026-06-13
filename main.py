"""
AFK - Away From Keyboard
Sprint 1: Hand & Eye Tracking Pipeline

Proof of concept (lanjutan Sprint 0):
- Menggunakan modul HandTracker untuk deteksi tangan + hitung jari terangkat
- Menggunakan modul FaceTracker untuk hitung diameter iris (estimasi jarak)
- Smoothing posisi fingertip & diameter iris dengan EMA
- Toggle aktif/nonaktif program via hotkey Win+A
"""

import cv2
from pynput import keyboard

from afk.tracker.hand_tracker import HandTracker
from afk.tracker.face_tracker import FaceTracker
from afk.utils.smoothing import EMASmoother


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
class AppState:
    def __init__(self):
        self.active = False  # Program mulai dalam keadaan nonaktif
        self.running = True  # Untuk keluar dari program (tombol 'q')

state = AppState()


# ---------------------------------------------------------------------------
# Hotkey listener: Win+A untuk toggle aktif/nonaktif
# ---------------------------------------------------------------------------
def start_hotkey_listener():
    COMBO = {keyboard.Key.cmd, keyboard.KeyCode.from_char('a')}
    current_keys = set()

    def on_press(key):
        if key in COMBO:
            current_keys.add(key)
            if all(k in current_keys for k in COMBO):
                state.active = not state.active
                status = "AKTIF" if state.active else "NONAKTIF"
                print(f"[Hotkey] Win+A ditekan -> Program {status}")

    def on_release(key):
        if key in current_keys:
            current_keys.discard(key)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()
    return listener


# ---------------------------------------------------------------------------
# Overlay
# ---------------------------------------------------------------------------
def draw_status_overlay(frame, state: AppState, finger_status: dict | None,
                         iris_diameter_px: float | None):
    h, w = frame.shape[:2]

    status_text = "AKTIF" if state.active else "NONAKTIF (Win+A untuk toggle)"
    status_color = (0, 255, 0) if state.active else (0, 0, 255)

    cv2.rectangle(frame, (0, 0), (w, 95), (30, 30, 30), -1)
    cv2.putText(frame, f"Status: {status_text}", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

    if finger_status is not None:
        finger_text = (
            f"Jari: telunjuk={int(finger_status['index'])} "
            f"tengah={int(finger_status['middle'])} "
            f"jempol={int(finger_status['thumb'])} "
            f"| total={finger_status['count']}"
        )
    else:
        finger_text = "Tangan: tidak terdeteksi"
    cv2.putText(frame, finger_text, (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    if iris_diameter_px is not None:
        iris_text = f"Diameter iris: {iris_diameter_px:.2f} px (proxy jarak mata-kamera)"
    else:
        iris_text = "Wajah: tidak terdeteksi"
    cv2.putText(frame, iris_text, (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)


def main():
    print("=" * 60)
    print("AFK - Away From Keyboard")
    print("Sprint 1: Hand & Eye Tracking Pipeline")
    print("=" * 60)
    print("Tekan Win+A untuk toggle AKTIF/NONAKTIF")
    print("Tekan 'q' pada window video untuk keluar")
    print("=" * 60)

    listener = start_hotkey_listener()

    hand_tracker = HandTracker(max_num_hands=1)
    face_tracker = FaceTracker()

    # Smoother untuk posisi fingertip (telunjuk) dan diameter iris.
    # alpha=0.5 dipilih sebagai titik awal: cukup responsif tapi sudah
    # meredam jitter kecil. Akan di-tuning di Sprint 3.
    index_tip_smoother = EMASmoother(alpha=0.5)
    iris_diameter_smoother = EMASmoother(alpha=0.3)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[Error] Tidak bisa membuka webcam. Cek koneksi kamera/permission.")
        return

    try:
        while cap.isOpened() and state.running:
            success, frame = cap.read()
            if not success:
                print("[Warning] Gagal membaca frame dari webcam.")
                continue

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False

            # --- Hand tracking ---
            hand_landmarks = hand_tracker.process(rgb_frame)
            finger_status = None
            smoothed_index_tip = None

            if hand_landmarks is not None:
                finger_status = HandTracker.count_raised_fingers(hand_landmarks)

                raw_index_tip = HandTracker.get_index_fingertip(hand_landmarks, w, h)
                smoothed_index_tip = index_tip_smoother.update(raw_index_tip)

                # Gambar titik fingertip (telunjuk = hijau, tengah = kuning)
                index_px = (int(smoothed_index_tip[0]), int(smoothed_index_tip[1]))
                cv2.circle(frame, index_px, 8, (0, 255, 0), -1)

                middle_px = HandTracker.get_middle_fingertip(hand_landmarks, w, h)
                cv2.circle(frame, middle_px, 6, (0, 255, 255), -1)
            else:
                index_tip_smoother.reset()

            # --- Face tracking (iris) ---
            face_landmarks = face_tracker.process(rgb_frame)
            smoothed_iris_diameter = None

            if face_landmarks is not None:
                raw_iris_diameter = face_tracker.iris_diameter_px(face_landmarks, w, h)
                smoothed_iris_diameter = iris_diameter_smoother.update(raw_iris_diameter)

                # Visualisasi titik iris (kiri & kanan, center saja)
                for idx in (468, 473):  # center iris kiri & kanan
                    px = FaceTracker.get_iris_landmark_px(face_landmarks, idx, w, h)
                    cv2.circle(frame, px, 3, (255, 0, 255), -1)
            else:
                iris_diameter_smoother.reset()

            # --- Overlay ---
            draw_status_overlay(frame, state, finger_status, smoothed_iris_diameter)

            cv2.imshow("AFK - Sprint 1 PoC", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                state.running = False
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        hand_tracker.close()
        face_tracker.close()
        listener.stop()
        print("[AFK] Program dihentikan.")


if __name__ == "__main__":
    main()