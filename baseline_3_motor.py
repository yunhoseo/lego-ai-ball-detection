"""
[baseline 3단계] 공 탐지 → 허브 A모터 1회전 (최종 목표!)

목표: 공을 보여주면 허브의 A모터가 한 바퀴 돌면 성공!
실행 전:
  1. baseline_2가 성공했어야 합니다.
  2. 허브에 spike_hub_a_once.py가 들어있어야 합니다. (가이드 4단계)
  3. Pybricks 브라우저 탭을 완전히 닫으세요.
  4. 허브를 "파란 깜빡임" 상태로 만드세요. (초록불이면 버튼 한 번)
실행 후: 카메라 창이 뜨면 → 허브 가운데 버튼을 눌러 초록불로!
종료: 카메라 창을 클릭하고 q 키
"""

import asyncio
import sys

import cv2
from ultralytics import YOLO
from bleak import BleakScanner, BleakClient

HUB_NAME = "Pybricks Hub"   # ★ 우리 팀 허브 이름으로 바꾸세요!
VIDEO_SOURCE = 1            # baseline_1에서 성공한 번호와 같게
CONF = 0.5

# 허브와 대화하는 블루투스 주소 (Pybricks 고정값, 바꾸지 마세요)
PYBRICKS_CHAR = "c5f50002-8280-46da-89f4-6d8051e4aeef"


async def main():
    print("AI 모델 로딩 중...")
    model = YOLO("best.pt")

    print(f'허브 "{HUB_NAME}" 검색 중... (허브가 파란 깜빡임인지 확인!)')
    device = None
    while device is None:
        device = await BleakScanner.find_device_by_name(HUB_NAME, timeout=10.0)
        if device is None:
            print("  아직 못 찾음. 허브를 파란 깜빡임으로 만들면 자동 연결됩니다...")

    async with BleakClient(device) as client:
        print("허브 연결 완료! 카메라를 엽니다.")

        if sys.platform == "darwin":
            cap = cv2.VideoCapture(VIDEO_SOURCE, cv2.CAP_AVFOUNDATION)
        else:
            cap = cv2.VideoCapture(VIDEO_SOURCE)

        if not cap.isOpened():
            print("카메라를 열 수 없습니다. VIDEO_SOURCE 숫자를 확인하세요.")
            return

        seen = 0      # 공이 연속으로 보인 프레임 수
        empty = 0     # 공이 안 보인 프레임 수
        armed = True  # True일 때만 모터 신호를 보냄 (공 하나당 딱 1번)

        print(">>> 카메라 창이 뜨면 허브 가운데 버튼을 눌러 초록불로 만드세요! <<<")
        print("공을 보여주면 모터가 돕니다. (q = 종료)")

        while True:
            ok, frame = cap.read()
            if not ok:
                await asyncio.sleep(0.1)
                continue

            r = model.predict(frame, conf=CONF, verbose=False)[0]

            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                label = model.names[int(box.cls[0])]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, max(30, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # 공 감지 안정화: 3프레임 연속 보여야 진짜 공으로 인정
            if len(r.boxes) > 0:
                seen += 1
                empty = 0
            else:
                seen = 0
                empty += 1
                if empty >= 3:
                    armed = True   # 공이 사라졌으니 다음 공 받을 준비

            if armed and seen >= 3:
                print("공 감지! → 허브에 모터 1회전 신호 전송")
                # b"\x06" = "이건 명령이야" 표시, b"d" = 우리가 정한 '돌아라' 신호
                await client.write_gatt_char(PYBRICKS_CHAR, b"\x06d", response=True)
                armed = False

            cv2.imshow("3. detect -> motor (q=quit)", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()

        print("허브에 종료 신호 전송")
        await client.write_gatt_char(PYBRICKS_CHAR, b"\x06q", response=True)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
