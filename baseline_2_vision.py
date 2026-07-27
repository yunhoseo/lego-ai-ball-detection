"""
[baseline 2단계] AI 공 탐지 테스트 (모터 없이 눈으로만 확인)

목표: 공을 비추면 초록 상자 + 공 이름 + 점수가 뜨면 성공!
실행 전: baseline_1이 성공했어야 합니다. best.pt 파일이 같은 폴더에 있어야 합니다.
종료: 카메라 창을 클릭하고 q 키
"""

import sys

import cv2
from ultralytics import YOLO

VIDEO_SOURCE = 1   # baseline_1에서 성공한 번호와 같게
CONF = 0.5         # 탐지 기준 점수(0~1). 공이 잘 안 잡히면 0.3으로 낮춰보세요.

print("AI 모델 로딩 중... (조금 걸려요)")
model = YOLO("best.pt")
print("이 AI가 알아보는 것들:", list(model.names.values()))

if sys.platform == "darwin":
    cap = cv2.VideoCapture(VIDEO_SOURCE, cv2.CAP_AVFOUNDATION)
else:
    cap = cv2.VideoCapture(VIDEO_SOURCE)

if not cap.isOpened():
    print("카메라를 열 수 없습니다. VIDEO_SOURCE 숫자를 확인하세요.")
    raise SystemExit

print("탐지 시작! 공을 카메라에 보여주세요. (q = 종료)")

while True:
    ok, frame = cap.read()
    if not ok:
        continue

    # AI에게 이 화면에 공이 있는지 물어본다
    r = model.predict(frame, conf=CONF, verbose=False)[0]

    # 찾은 공마다 초록 상자를 그린다
    for box in r.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        label = model.names[int(box.cls[0])]      # 공 이름 (red_normal 등)
        conf = float(box.conf[0])                 # AI의 확신 정도 (0~1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, f"{label} {conf:.2f}", (x1, max(30, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imshow("2. vision test (q=quit)", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
