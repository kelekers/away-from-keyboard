"""
AFK - Away From Keyboard
Sprint 4: Gesture Klik

Penambahan dari Sprint 3:
- Integrasi ClickGestureDetector: saat gesture 2 jari (telunjuk + tengah)
  aktif, gerakan CEPAT ke atas dari jari tengah (velocity-based) memicu
  klik kiri via CursorController.click("left").
- Klik di-trigger pada posisi kursor TERAKHIR (hasil mapping dari jari
  telunjuk), bukan posisi jari tengah - sehingga klik terjadi tepat di
  lokasi yang sedang ditunjuk.
- Cooldown/debounce mencegah klik berulang dari satu gesture yang sama.
- Overlay menampilkan indikator visual saat klik ter-trigger.
"""

import cv2
from pynput import keyboard

try:
    import pyautogui
    SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
except Exception:
    # Fallback jika tidak ada display (misal environment tanpa GUI).
    # Di laptop asli, pyautogui.size() akan berhasil.
    SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080
    print("[Warning] Tidak bisa mendapatkan ukuran layar via pyautogui, "
          f"menggunakan default {SCREEN_WIDTH}x{SCREEN_HEIGHT}.")

from afk.tracker.hand_tracker import HandTracker
from afk.tracker.face_tracker import FaceTracker
from afk.utils.smoothing import EMASmoother
from afk.calibration import CalibrationManager
from afk.cursor_controller import CursorController
from afk.click_gesture import ClickGestureDetector


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
class AppState:
    def __init__(self):
        self.active = False  # Program mulai dalam keadaan nonaktif
        self.running = True  # Untuk keluar dari program (tombol 'q')
        self.request_calibration = False  # diset True saat tombol 'c' ditekan

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
                         iris_diameter_px: float | None,
                         calibration_manager: CalibrationManager,
                         mapped_screen_pos: tuple | None,
                         cursor_control_active: bool,
                         click_triggered: bool):
    h, w = frame.shape[:2]

    status_text = "AKTIF" if state.active else "NONAKTIF (Win+A untuk toggle)"
    status_color = (0, 255, 0) if state.active else (0, 0, 255)

    cv2.rectangle(frame, (0, 0), (w, 145), (30, 30, 30), -1)
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
    cv2.putText(frame, finger_text, (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    if iris_diameter_px is not None:
        iris_text = f"Diameter iris: {iris_diameter_px:.2f} px"
    else:
        iris_text = "Wajah: tidak terdeteksi"
    cv2.putText(frame, iris_text, (10, 75),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    if calibration_manager.is_calibrated:
        calib_text = "Kalibrasi: SUDAH ('c' untuk ulang)"
        calib_color = (0, 255, 0)
    else:
        calib_text = "Kalibrasi: BELUM (tekan 'c' untuk mulai)"
        calib_color = (0, 165, 255)
    cv2.putText(frame, calib_text, (10, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, calib_color, 1)

    cursor_text = "Kontrol kursor: AKTIF (mode 1 jari)" if cursor_control_active else "Kontrol kursor: nonaktif"
    cursor_color = (0, 255, 0) if cursor_control_active else (150, 150, 150)
    cv2.putText(frame, cursor_text, (10, 125),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, cursor_color, 1)

    if mapped_screen_pos is not None:
        sx, sy = mapped_screen_pos
        preview_text = f"Posisi layar: ({sx:.0f}, {sy:.0f}) / {calibration_manager.screen_width}x{calibration_manager.screen_height}"
        cv2.putText(frame, preview_text, (10, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

    # Indikator visual besar saat klik ter-trigger
    if click_triggered:
        cv2.putText(frame, "KLIK!", (w // 2 - 60, h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 255), 4)
        cv2.circle(frame, (w // 2, h // 2 + 50), 20, (0, 0, 255), -1)


def draw_calibration_overlay(frame, calibration_manager: CalibrationManager,
                              fingertip_px: tuple | None, two_finger_gesture: bool):
    """Overlay khusus saat mode kalibrasi aktif."""
    h, w = frame.shape[:2]

    # Banner instruksi
    cv2.rectangle(frame, (0, h - 100), (w, h), (40, 40, 40), -1)

    step_idx, total_steps = calibration_manager.progress
    instruction = calibration_manager.current_instruction

    cv2.putText(frame, f"KALIBRASI ({step_idx + 1}/{total_steps})",
                (10, h - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(frame, instruction, (10, h - 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.putText(frame, "Tunjukkan 2 jari (telunjuk + tengah) dan TAHAN posisi",
                (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    # Progress bar "hold to confirm"
    hold_progress = calibration_manager.hold_progress
    bar_width = int(200 * hold_progress)
    bar_color = (0, 255, 0) if two_finger_gesture else (0, 0, 255)
    cv2.rectangle(frame, (w - 220, h - 70), (w - 220 + 200, h - 50), (100, 100, 100), 1)
    cv2.rectangle(frame, (w - 220, h - 70), (w - 220 + bar_width, h - 50), bar_color, -1)

    if not two_finger_gesture:
        cv2.putText(frame, "Tunjukkan gesture 2 jari!", (w - 220, h - 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    # Tandai posisi fingertip dengan warna mencolok saat kalibrasi
    if fingertip_px is not None:
        color = (0, 255, 0) if two_finger_gesture else (0, 0, 255)
        px = (int(fingertip_px[0]), int(fingertip_px[1]))
        cv2.circle(frame, px, 12, color, 2)
        cv2.circle(frame, px, 2, color, -1)


def main():
    print("=" * 60)
    print("AFK - Away From Keyboard")
    print("Sprint 4: Gesture Klik")
    print("=" * 60)
    print("Tekan Win+A untuk toggle AKTIF/NONAKTIF")
    print("Tekan 'c' untuk mulai/ulang kalibrasi")
    print("Tekan 'q' pada window video untuk keluar")
    print("Mode kursor : 1 jari (telunjuk saja) untuk menggerakkan kursor")
    print("Mode klik   : 2 jari (telunjuk+tengah), lalu sentil jari tengah ke ATAS")
    print("=" * 60)
    print(f"Resolusi layar terdeteksi: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")

    listener = start_hotkey_listener()

    hand_tracker = HandTracker(max_num_hands=1)
    face_tracker = FaceTracker()
    calibration_manager = CalibrationManager(SCREEN_WIDTH, SCREEN_HEIGHT)
    cursor_controller = CursorController(SCREEN_WIDTH, SCREEN_HEIGHT)
    click_detector = ClickGestureDetector()

    # Coba load kalibrasi yang sudah ada
    if calibration_manager.load():
        print(f"[Kalibrasi] Berhasil memuat kalibrasi dari {calibration_manager.config_path}")
        # Set referensi iris diameter ke FaceTracker agar distance_ratio()
        # dari FaceTracker (jika dipakai di sprint berikutnya) konsisten
        face_tracker.set_reference_iris_diameter(calibration_manager.data.reference_iris_diameter_px)
    else:
        print("[Kalibrasi] Belum ada data kalibrasi. Tekan 'c' untuk mulai kalibrasi.")

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
            two_finger_gesture = False
            one_finger_gesture = False
            raw_middle_y = None

            if hand_landmarks is not None:
                finger_status = HandTracker.count_raised_fingers(hand_landmarks)

                raw_index_tip = HandTracker.get_index_fingertip(hand_landmarks, w, h)
                smoothed_index_tip = index_tip_smoother.update(raw_index_tip)

                # Gesture 2 jari: telunjuk + tengah terangkat, jari lain tidak
                # Dipakai untuk kalibrasi (Sprint 2) dan klik (Sprint 4).
                two_finger_gesture = (
                    finger_status["index"] and finger_status["middle"]
                    and not finger_status["ring"] and not finger_status["pinky"]
                )

                # Gesture 1 jari: hanya telunjuk terangkat. Dipakai untuk
                # menggerakkan kursor (Sprint 3).
                one_finger_gesture = (
                    finger_status["index"] and not finger_status["middle"]
                    and not finger_status["ring"] and not finger_status["pinky"]
                )

                index_px = (int(smoothed_index_tip[0]), int(smoothed_index_tip[1]))
                middle_px = HandTracker.get_middle_fingertip(hand_landmarks, w, h)
                raw_middle_y = middle_px[1]  # posisi Y mentah (tidak smoothed) untuk click detector

                index_color = (0, 255, 0) if (one_finger_gesture or two_finger_gesture) else (0, 200, 0)
                cv2.circle(frame, index_px, 8, index_color, -1)
                cv2.circle(frame, middle_px, 6, (0, 255, 255), -1)
            else:
                index_tip_smoother.reset()

            # --- Face tracking (iris) ---
            face_landmarks = face_tracker.process(rgb_frame)
            smoothed_iris_diameter = None

            if face_landmarks is not None:
                raw_iris_diameter = face_tracker.iris_diameter_px(face_landmarks, w, h)
                smoothed_iris_diameter = iris_diameter_smoother.update(raw_iris_diameter)

                for idx in (468, 473):
                    px = FaceTracker.get_iris_landmark_px(face_landmarks, idx, w, h)
                    cv2.circle(frame, px, 3, (255, 0, 255), -1)
            else:
                iris_diameter_smoother.reset()

            # --- Trigger kalibrasi manual ---
            if state.request_calibration and not calibration_manager.is_calibrating:
                calibration_manager.start()
                state.request_calibration = False
                print("[Kalibrasi] Dimulai. Ikuti instruksi di layar.")

            # --- Proses kalibrasi jika sedang berjalan ---
            if calibration_manager.is_calibrating:
                confirmed = calibration_manager.update(
                    smoothed_index_tip, smoothed_iris_diameter, two_finger_gesture
                )
                if confirmed:
                    step_idx, total = calibration_manager.progress
                    print(f"[Kalibrasi] Titik {step_idx}/{total} dikonfirmasi.")

                if not calibration_manager.is_calibrating and calibration_manager.is_calibrated:
                    # Baru saja selesai kalibrasi pada frame ini
                    calibration_manager.set_frame_size(w, h)
                    calibration_manager.save()
                    face_tracker.set_reference_iris_diameter(
                        calibration_manager.data.reference_iris_diameter_px
                    )
                    print(f"[Kalibrasi] Selesai! Data tersimpan ke {calibration_manager.config_path}")
                    print(f"[Kalibrasi] Data: {calibration_manager.data}")

                draw_calibration_overlay(frame, calibration_manager, smoothed_index_tip, two_finger_gesture)

            # --- Mapping ke koordinat layar & gerakkan kursor (jika sudah dikalibrasi) ---
            mapped_screen_pos = None
            cursor_control_active = False
            click_triggered = False

            if (calibration_manager.is_calibrated and not calibration_manager.is_calibrating
                    and smoothed_index_tip is not None):
                mapped_screen_pos = calibration_manager.map_to_screen(
                    smoothed_index_tip, smoothed_iris_diameter
                )

                # Kontrol kursor hanya jika: program aktif (Win+A) DAN
                # gesture 1 jari terdeteksi (mode gerak kursor, bukan klik).
                cursor_control_active = state.active and one_finger_gesture

                if cursor_control_active:
                    cursor_controller.move_to(*mapped_screen_pos)

                # --- Deteksi gesture klik (gerakan cepat ke atas jari tengah) ---
                # Hanya aktif jika program aktif (Win+A). Klik di-trigger pada
                # posisi kursor saat ini (mapped_screen_pos dari jari telunjuk),
                # bukan posisi jari tengah.
                if state.active:
                    click_triggered = click_detector.update(two_finger_gesture, raw_middle_y)
                    if click_triggered:
                        cx, cy = cursor_controller.clamp(*mapped_screen_pos)
                        cursor_controller.move_to(cx, cy)  # pastikan kursor di posisi yang benar sebelum klik
                        cursor_controller.click("left")
                        print(f"[Klik] Klik kiri di ({cx}, {cy})")
                else:
                    click_detector.reset()
            else:
                click_detector.reset()

            # --- Overlay status umum (selalu ditampilkan) ---
            draw_status_overlay(frame, state, finger_status, smoothed_iris_diameter,
                                 calibration_manager, mapped_screen_pos, cursor_control_active,
                                 click_triggered)

            cv2.imshow("AFK - Sprint 4 PoC", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                state.running = False
                break
            elif key == ord('c'):
                state.request_calibration = True
    finally:
        cap.release()
        cv2.destroyAllWindows()
        hand_tracker.close()
        face_tracker.close()
        listener.stop()
        print("[AFK] Program dihentikan.")


if __name__ == "__main__":
    main()