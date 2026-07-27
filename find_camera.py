"""
카메라 인덱스 찾기 도우미.

macOS 연속성 카메라(iPhone)가 몇 번 인덱스인지 확인하는 스크립트.
1) AVFoundation이 인식한 실제 카메라 이름 + 인덱스 표를 먼저 출력하고,
2) 각 인덱스를 하나씩 열어 미리보기 창을 띄운다.

사용법:
    python find_camera.py

조작(미리보기 창에서):
    n  → 다음 카메라로
    s  → 지금 인덱스를 VIDEO_SOURCE 값으로 출력하고 종료
    q  → 그냥 종료

주의:
    - 처음 실행 시 macOS 카메라 권한 팝업이 뜨면 '허용'.
      (시스템 설정 > 개인정보 보호 및 보안 > 카메라)
    - iPhone은 '잠금 + 거치 고정 + 후면 카메라가 대상' 상태여야
      연속성 카메라로 잡힌다. 손에 들거나 잠금 해제하면 내장캠으로 폴백된다.
"""

import sys
import cv2

MAX_INDEX = 6


def print_avf_devices():
    """AVFoundation이 보는 카메라 이름 목록을 인덱스와 함께 출력(가능할 때만)."""
    try:
        import AVFoundation as AVF
    except Exception:
        print("(AVFoundation 목록 조회 불가 — 미리보기로만 확인하세요)\n")
        return

    try:
        devs = AVF.AVCaptureDevice.devicesWithMediaType_(AVF.AVMediaTypeVideo)
    except Exception:
        devs = None

    print("=== macOS가 인식한 카메라 (보통 이 순서 = OpenCV 인덱스) ===")
    if not devs:
        print("  (없음) iPhone이 연속성 카메라로 송출 중인지 확인하세요.")
    else:
        for i, d in enumerate(devs):
            print(f"  index {i}: {d.localizedName()}")
    print()


def make_cap(idx):
    if sys.platform == "darwin":
        return cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
    return cv2.VideoCapture(idx)


def main():
    print_avf_devices()

    found = []

    for idx in range(MAX_INDEX):
        cap = make_cap(idx)

        if not cap.isOpened():
            cap.release()
            continue

        ok = False
        frame = None
        for _ in range(10):
            ok, frame = cap.read()

        if not ok:
            cap.release()
            continue

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"index {idx}: 열림 {w}x{h}  -> iPhone 화면이면 s, 아니면 n")
        found.append(idx)

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            cv2.putText(
                frame,
                f"index {idx}  {w}x{h}  (n=next, s=select, q=quit)",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )
            cv2.imshow("find_camera", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("n"):
                break

            if key == ord("s"):
                cap.release()
                cv2.destroyAllWindows()
                print()
                print(f"[선택됨] index {idx}")
                print("balldetection_1.py 에서 다음처럼 설정하세요:")
                print(f"    VIDEO_SOURCE = {idx}")
                return

            if key == ord("q"):
                cap.release()
                cv2.destroyAllWindows()
                return

        cap.release()

    cv2.destroyAllWindows()

    if not found:
        print("열리는 카메라가 없습니다.")
        print("  - iPhone: 연속성 카메라 ON + 잠금 + 거치 고정 + 같은 Apple ID + WiFi/BT ON")
        print("  - 카메라 권한 허용 후 앱(터미널/VSCode) 재시작")
    else:
        print(f"열린 인덱스: {found}")


if __name__ == "__main__":
    main()
