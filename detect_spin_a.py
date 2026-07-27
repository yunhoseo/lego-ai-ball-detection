"""
탐지되면 허브 A 모터 1회전 (색상 분류 없는 테스트용).

detect_only.py처럼 카메라를 열어 YOLO 박스를 화면에 그려 보여주면서,
공이 연속 REQUIRED_OBJECT_FRAMES 프레임 이상 잡히면 허브에 "d"를 보낸다.
허브 쪽은 spike_hub_a_once.py를 먼저 다운로드해 실행해야 한다
(A 모터만 있고, 받으면 1회전 후 대기).

사용법:
    python detect_spin_a.py

조작:
    q  → 종료 (허브에 종료 코드 전송)
"""

import asyncio
import sys
import time
from contextlib import suppress

import cv2
from ultralytics import YOLO
from bleak import BleakScanner, BleakClient

PYBRICKS_COMMAND_EVENT_CHAR_UUID = "c5f50002-8280-46da-89f4-6d8051e4aeef"

HUB_NAME = "Pybricks Hub"
MODEL_PATH = "best.pt"

VIDEO_SOURCE = 1          # 1 = iPhone (연속성 카메라)
CAM_WIDTH = 1280
CAM_HEIGHT = 720

CONF = 0.5

# 공 하나당 한 번만 트리거되도록: 연속 감지 프레임 / 연속 빈 프레임 조건
REQUIRED_OBJECT_FRAMES = 3
REQUIRED_EMPTY_FRAMES = 3


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


async def main():
    ready_event = asyncio.Event()

    def handle_disconnect(_):
        print("Hub disconnected.")

    def handle_rx(_, data: bytearray):
        if data and data[0] == 0x01:
            payload = data[1:].strip()
            # 허브가 뭐라도 응답하면 로그 (모터 처리 후 rdy를 보냄 → 허브 실행 중 확인용)
            print(f"[허브 응답] {payload}")
            if payload == b"rdy":
                ready_event.set()

    async def send_code(client, code: str):
        # rdy 핸드셰이크 없이 바로 전송 (허브 프로그램이 실행 중이면 즉시 처리됨)
        await client.write_gatt_char(
            PYBRICKS_COMMAND_EVENT_CHAR_UUID,
            b"\x06" + code.encode("utf-8"),
            response=True,
        )
        print(f"[전송 완료] code={code}")

    print("YOLO 모델 로딩 중...")
    model = YOLO(MODEL_PATH)
    print("클래스:", model.names)

    print("허브 검색 중... (허브를 '파란 점멸'=연결 대기 상태로 두세요)")
    print("  ※ 초록불이면 검색에 안 잡힙니다 → 허브 버튼 눌러 프로그램을 멈춰 파란 점멸로.")
    device = None
    for attempt in range(1, 19):  # 10초 x 18회 = 최대 3분 대기
        device = await BleakScanner.find_device_by_name(HUB_NAME, timeout=10.0)
        if device is not None:
            break
        print(f"  [{attempt}] 아직 못 찾음, 재시도 중... (허브를 파란 점멸로 두면 자동 연결)")
    if device is None:
        print(f"허브를 찾지 못했습니다: {HUB_NAME}")
        print("확인: Pybricks Code 브라우저 탭 닫기, 허브 전원, 파란 점멸 여부")
        return

    print("허브 찾음:", device.name)

    async with BleakClient(device, disconnected_callback=handle_disconnect) as client:
        await client.start_notify(PYBRICKS_COMMAND_EVENT_CHAR_UUID, handle_rx)

        print("허브 연결 완료. 카메라를 엽니다.")
        print(">>> 카메라 창이 뜨면, 허브 가운데 버튼을 눌러 프로그램을 시작(초록불)해 두세요. <<<")

        print(f"카메라 여는 중... (source={VIDEO_SOURCE})")
        cap = open_camera(VIDEO_SOURCE)
        if cap is None:
            print("카메라를 열 수 없습니다. find_camera.py로 인덱스 확인하세요.")
            return

        object_seen_frames = 0
        empty_count = 0
        armed = True  # True면 다음 감지 시 트리거 가능

        read_fail_count = 0
        max_read_fail = 30

        print("실시간 탐지 시작. 종료하려면 q를 누르세요.")

        while True:
            ok, frame = cap.read()

            if not ok:
                read_fail_count += 1
                if read_fail_count >= max_read_fail:
                    print("프레임을 계속 읽지 못해 종료합니다.")
                    break
                await asyncio.sleep(0.1)
                continue
            read_fail_count = 0

            r = model.predict(frame, conf=CONF, verbose=False)[0]
            n = len(r.boxes) if r.boxes is not None else 0
            object_visible = n > 0

            if r.boxes is not None:
                for b in r.boxes:
                    x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
                    conf = float(b.conf[0])
                    label = model.names[int(b.cls[0])]
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(
                        frame, f"{label} {conf:.2f}", (x1, max(30, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
                    )

            if object_visible:
                object_seen_frames += 1
                empty_count = 0
            else:
                object_seen_frames = 0
                empty_count += 1
                if empty_count >= REQUIRED_EMPTY_FRAMES:
                    armed = True

            if armed and object_seen_frames >= REQUIRED_OBJECT_FRAMES:
                print(f"[공 연속 {REQUIRED_OBJECT_FRAMES}프레임 감지 → A모터 1회전 명령 전송]")
                await send_code(client, "d")
                armed = False

            cv2.putText(
                frame,
                f"dets:{n}  armed:{armed}  (q=quit)",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )
            cv2.imshow("detect -> A motor spin (q=quit)", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()

        print("종료 코드 전송")
        await send_code(client, "q")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    with suppress(asyncio.CancelledError):
        asyncio.run(main())
