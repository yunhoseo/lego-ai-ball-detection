"""
[baseline 1단계] 휴대폰 카메라 연결 테스트

목표: 폰 카메라 화면이 노트북 창에 나오면 성공!
실행 전: Iriun 앱(폰) + Iriun 프로그램(노트북)이 켜져 있어야 합니다.
종료: 카메라 창을 클릭하고 q 키
"""

import sys

import cv2

# 폰 카메라 번호. 내 얼굴(노트북 내장캠)이 나오면 0, 1, 2로 바꿔보세요.
VIDEO_SOURCE = 1

if sys.platform == "darwin":  # 맥에서 테스트할 때용 (Windows는 아래 줄로 실행됨)
    cap = cv2.VideoCapture(VIDEO_SOURCE, cv2.CAP_AVFOUNDATION)
else:
    cap = cv2.VideoCapture(VIDEO_SOURCE)

if not cap.isOpened():
    print("카메라를 열 수 없습니다. VIDEO_SOURCE 숫자를 바꿔서 다시 실행해 보세요.")
    raise SystemExit

print("카메라 열림! 폰 화면이 나오는지 확인하세요. (q = 종료)")

while True:
    ok, frame = cap.read()
    if not ok:
        continue

    cv2.imshow("1. camera test (q=quit)", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
