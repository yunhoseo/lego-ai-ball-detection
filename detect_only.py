"""
탐지 전용 뷰어 (LEGO 허브 없이 카메라 + YOLO만).

balldetection_1.py 는 허브 BLE 연결이 돼야 시작되지만,
이 스크립트는 허브 없이 iPhone 카메라 영상에 YOLO 박스를 그려
'탐지가 되는지'만 눈으로 확인한다.

사용법:
    python detect_only.py

조작:
    q  → 종료

확인 포인트:
    - 공을 카메라 앞에 두면 박스 + 클래스명(red_normal 등) + conf 가 뜬다.
    - 안 뜨면: 초점/거리/조명이 학습 구도와 다를 가능성 → 공이 선명히
      크게 보이도록 폰 위치를 맞춰본다.
"""

import sys
import time

import cv2
from ultralytics import YOLO

MODEL_PATH = "best.pt"

VIDEO_SOURCE = 1          # 1 = iPhone (연속성 카메라)
CAM_WIDTH = 1280
CAM_HEIGHT = 720

# 낮게 잡아 뭐든 잡히는지 먼저 본다 (balldetection 본 코드는 0.5)
# 실행 중 - / = 키로 실시간 조절 가능
CONF = 0.10


def open_camera(source, retries=6, delay=1.0):
    for attempt in range(1, retries + 1):
        if isinstance(source, int) and sys.platform == "darwin":
            cap = cv2.VideoCapture(source, cv2.CAP_AVFOUNDATION)
        else:
            cap = cv2.VideoCapture(source)

        if cap.isOpened():
            if isinstance(source, int):
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
            ok = False
            for _ in range(10):
                ok, _ = cap.read()
            if ok:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"[카메라 열림] source={source}, {w}x{h}")
                return cap

        cap.release()
        print(f"[재시도 {attempt}/{retries}] source={source}")
        time.sleep(delay)
    return None


def main():
    print("모델 로딩...")
    model = YOLO(MODEL_PATH)
    print("클래스:", model.names)

    cap = open_camera(VIDEO_SOURCE)
    if cap is None:
        print("카메라를 열 수 없습니다. (iPhone 연속성 카메라/권한 확인)")
        return

    print("탐지 시작.  q=종료,  '-'=conf 내리기,  '='(또는 '+')=conf 올리기")
    prev = time.time()
    fps = 0.0
    conf = CONF

    while True:
        ok, frame = cap.read()
        if not ok:
            print("프레임 읽기 실패, 재시도...")
            time.sleep(0.1)
            continue

        r = model.predict(frame, conf=conf, verbose=False)[0]

        # 클래스별 최고 conf 집계 (초록/빨강 등 무엇이 얼마나 잡히나 확인용)
        best_per_cls = {}
        n = 0
        if r.boxes is not None:
            n = len(r.boxes)
            for b in r.boxes:
                cls = model.names[int(b.cls[0])]
                c = float(b.conf[0])
                best_per_cls[cls] = max(best_per_cls.get(cls, 0.0), c)
                x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    f"{cls} {c:.2f}",
                    (x1, max(30, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )

        now = time.time()
        dt = now - prev
        prev = now
        if dt > 0:
            fps = 0.9 * fps + 0.1 * (1.0 / dt)

        cv2.putText(
            frame,
            f"dets: {n}   conf>={conf:.2f}   fps: {fps:.1f}   (-/= conf, q quit)",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )

        # 잡힌 클래스별 최고 점수 표시
        y = 65
        for cls, c in sorted(best_per_cls.items()):
            cv2.putText(
                frame,
                f"{cls}: {c:.2f}",
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            y += 28

        cv2.imshow("detect_only (q=quit)", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key in (ord("-"), ord("_")):
            conf = max(0.01, round(conf - 0.05, 2))
            print(f"conf -> {conf:.2f}")
        elif key in (ord("="), ord("+")):
            conf = min(0.95, round(conf + 0.05, 2))
            print(f"conf -> {conf:.2f}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
