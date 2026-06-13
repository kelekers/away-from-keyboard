"""
AFK - Away From Keyboard
Sprint 0: Setup & Riset Dasar

Proof of concept:
- Capture webcam real-time
- Render landmark wajah (iris) & tangan menggunakan MediaPipe
- Toggle aktif/nonaktif program via hotkey Win+A
"""

import cv2
import mediapipe as mp
import threading
from pynput import keyboard

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
    """
    Mendengarkan kombinasi tombol Win+A secara global.
    Saat ditekan, toggle state.active.
    """
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
# MediaPipe setup
# ---------------------------------------------------------------------------
mp_face_mesh = mp.solutions.face_mesh
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Landmark index untuk iris (refine_landmarks=True diperlukan)
LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]


def draw_status_overlay(frame, state: AppState, num_hands: int, face_detected: bool):
    """Menampilkan indikator status program di pojok kiri atas frame."""
    h, w = frame.shape[:2]

    status_text = "AKTIF" if state.active else "NONAKTIF (Win+A untuk toggle)"
    status_color = (0, 255, 0) if state.active else (0, 0, 255)

    cv2.rectangle(frame, (0, 0), (w, 70), (30, 30, 30), -1)
    cv2.putText(frame, f"Status: {status_text}", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
    cv2.putText(frame, f"Tangan terdeteksi: {num_hands} | Wajah: {'Ya' if face_detected else 'Tidak'}",
                (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)


def main():
    print("=" * 60)
    print("AFK - Away From Keyboard")
    print("Sprint 0: Setup & Riset Dasar (Proof of Concept)")
    print("=" * 60)
    print("Tekan Win+A untuk toggle AKTIF/NONAKTIF")
    print("Tekan 'q' pada window video untuk keluar")
    print("=" * 60)

    listener = start_hotkey_listener()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[Error] Tidak bisa membuka webcam. Cek koneksi kamera/permission.")
        return

    with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,  # diperlukan untuk landmark iris
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as face_mesh, mp_hands.Hands(
        max_num_hands=1,  # bebas tangan kiri/kanan, hanya 1 tangan
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as hands:

        while cap.isOpened() and state.running:
            success, frame = cap.read()
            if not success:
                print("[Warning] Gagal membaca frame dari webcam.")
                continue

            # Flip horizontal supaya seperti cermin (lebih intuitif untuk user)
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False

            face_results = face_mesh.process(rgb_frame)
            hand_results = hands.process(rgb_frame)

            num_hands = 0
            face_detected = False

            # --- Render hand landmarks ---
            if hand_results.multi_hand_landmarks:
                num_hands = len(hand_results.multi_hand_landmarks)
                for hand_landmarks in hand_results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style(),
                    )

            # --- Render face/iris landmarks ---
            if face_results.multi_face_landmarks:
                face_detected = True
                h, w = frame.shape[:2]
                for face_landmarks in face_results.multi_face_landmarks:
                    # Gambar titik iris kiri & kanan (untuk estimasi jarak nanti)
                    for idx in LEFT_IRIS + RIGHT_IRIS:
                        lm = face_landmarks.landmark[idx]
                        cx, cy = int(lm.x * w), int(lm.y * h)
                        cv2.circle(frame, (cx, cy), 2, (255, 0, 255), -1)

            # --- Overlay status ---
            draw_status_overlay(frame, state, num_hands, face_detected)

            cv2.imshow("AFK - Sprint 0 PoC", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                state.running = False
                break

    cap.release()
    cv2.destroyAllWindows()
    listener.stop()
    print("[AFK] Program dihentikan.")


if __name__ == "__main__":
    main()