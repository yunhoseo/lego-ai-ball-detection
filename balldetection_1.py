import asyncio
import sys
import time
from contextlib import suppress

import cv2
from ultralytics import YOLO
from bleak import BleakScanner, BleakClient


# =========================
# 1. Pybricks 통신 설정
# =========================

PYBRICKS_COMMAND_EVENT_CHAR_UUID = "c5f50002-8280-46da-89f4-6d8051e4aeef"

HUB_NAME = "Pybricks Hub"
MODEL_PATH = "best.pt"

# =========================
# 1-1. 영상 입력 설정
# =========================

# 영상 소스
#   - 정수: 카메라 인덱스
#       macOS 연속성 카메라(iPhone) = 보통 1, 맥북 내장캠 = 0
#   - 문자열: 스트림 URL (예: "http://192.168.0.10:8080/video")
# 어느 인덱스가 iPhone인지 모르면 find_camera.py를 먼저 실행해 확인하세요.
VIDEO_SOURCE = 1

# 캡처 해상도 (iPhone은 기본 고해상도라 YOLO 속도를 위해 낮춰서 받는다)
CAM_WIDTH = 1280
CAM_HEIGHT = 720

# 카메라 zoom (CAP_PROP_ZOOM). None이면 설정 안 함.
# test_zoom.py로 화면이 실제로 바뀌는 걸 확인한 값만 넣으세요.
# (macOS 연속성 카메라에선 대개 무시됨 → 그땐 폰을 물리적으로 뒤로)
CAM_ZOOM = None


# =========================
# 2. YOLO class → 허브 코드 변환
# =========================

CLASS_TO_CODE = {
    "red_normal": "0",
    "red_detection": "1",
    "blue_normal": "2",
    "blue_detection": "3",
    "green_normal": "4",
    "green_detection": "5",
}

NG_CLASSES = {"scratch", "crack", "contamination", "defect", "ng", "detection"}
OK_CLASSES = {"ok", "normal"}


# =========================
# 3. 판정 기준
# =========================

# YOLO 기본 탐지 confidence
# 기존 0.25는 너무 낮아서 배경 오탐으로 D모터가 돌 수 있음
YOLO_PREDICT_CONF = 0.5

# detection 클래스가 이 점수 이상 한 번이라도 나오면 불량
DETECTION_CONF_THRESHOLD = 0.945

# normal 클래스가 이 점수 이상일 때만 정상으로 인정
NORMAL_CONF_THRESHOLD = 0.5

# D모터가 돈 뒤 최종 판정을 누적하는 시간
CLASSIFY_TIME = 0.7

# 공이 1프레임만 잡혀도 d를 보내지 않도록 연속 감지 프레임 조건 추가
REQUIRED_OBJECT_FRAMES = 3

# 너무 작은 박스는 오탐으로 보고 무시
MIN_BBOX_AREA = 500


# =========================
# 4. 색상/코드 변환 함수
# =========================

def get_color_from_label(label):
    if label is None:
        return None

    if "red" in label:
        return "red"

    if "blue" in label:
        return "blue"

    if "green" in label:
        return "green"

    return None


def get_detection_code_by_color(color):
    if color == "red":
        return "1"

    if color == "blue":
        return "3"

    if color == "green":
        return "5"

    if color == "orange":
        return "1"

    if color == "white":
        return "3"

    return None


def get_normal_code_by_color(color):
    if color == "red":
        return "0"

    if color == "blue":
        return "2"

    if color == "green":
        return "4"

    if color == "orange":
        return "0"

    if color == "white":
        return "2"

    return None


def detect_color_from_bbox(frame, xyxy):
    x1, y1, x2, y2 = map(int, xyxy)

    h, w = frame.shape[:2]
    x1 = max(0, min(x1, w - 1))
    x2 = max(0, min(x2, w - 1))
    y1 = max(0, min(y1, h - 1))
    y2 = max(0, min(y2, h - 1))

    roi = frame[y1:y2, x1:x2]

    if roi.size == 0:
        return None

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mean_h = hsv[:, :, 0].mean()
    mean_s = hsv[:, :, 1].mean()

    if mean_s < 50:
        return "white"

    if mean_h < 10 or mean_h > 170:
        return "red"

    if 10 <= mean_h < 25:
        return "orange"

    if 35 <= mean_h <= 85:
        return "green"

    if 90 <= mean_h <= 130:
        return "blue"

    return None


def get_valid_boxes(r):
    """
    YOLO 결과에서 너무 작은 박스를 제거한 유효 박스만 반환.
    """
    valid_boxes = []

    if r.boxes is None or len(r.boxes) == 0:
        return valid_boxes

    for box in r.boxes:
        xyxy = box.xyxy[0].tolist()
        x1, y1, x2, y2 = xyxy

        area = max(0, x2 - x1) * max(0, y2 - y1)

        if area >= MIN_BBOX_AREA:
            valid_boxes.append(box)

    return valid_boxes


def open_camera(source, retries=6, delay=1.0):
    """
    카메라/스트림을 연다.
    - macOS에서 정수 인덱스는 AVFoundation 백엔드를 명시해 연속성 카메라(iPhone)
      인식률을 높인다.
    - 연속성 카메라는 처음 깨어날 때 몇 초 걸릴 수 있어 여러 번 재시도한다.
    성공 시 VideoCapture, 실패 시 None 반환.
    """
    for attempt in range(1, retries + 1):
        if isinstance(source, int) and sys.platform == "darwin":
            cap = cv2.VideoCapture(source, cv2.CAP_AVFOUNDATION)
        else:
            cap = cv2.VideoCapture(source)

        if cap.isOpened():
            if isinstance(source, int):
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)

                if CAM_ZOOM is not None:
                    cap.set(cv2.CAP_PROP_ZOOM, CAM_ZOOM)

            # 워밍업: 첫 프레임이 안정될 때까지 몇 장 버린다
            ok = False
            for _ in range(10):
                ok, _ = cap.read()

            if ok:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(f"[카메라 열림] source={source}, {w}x{h}")
                return cap

        cap.release()
        print(f"[카메라 열기 재시도 {attempt}/{retries}] source={source}")
        time.sleep(delay)

    return None


# =========================
# 5. 메인 실행
# =========================

async def main():
    main_task = asyncio.current_task()
    ready_event = asyncio.Event()

    def handle_disconnect(_):
        print("Hub disconnected.")
        if not main_task.done():
            main_task.cancel()

    def handle_rx(_, data: bytearray):
        if data and data[0] == 0x01:
            payload = data[1:]

            if payload.strip() == b"rdy":
                print("[허브 수신] rdy")
                ready_event.set()

            elif payload.strip() == b"OK":
                print("Hub: OK")

            elif payload.strip() == b"IGN":
                print("Hub: IGN")

            elif payload.strip() == b"ER":
                print("Hub: ER")

            else:
                print("Hub:", payload)

    async def send_code(client, code: str):
        """
        허브가 rdy를 보낼 때까지 기다린 뒤 코드 전송.
        """
        await ready_event.wait()
        ready_event.clear()

        await client.write_gatt_char(
            PYBRICKS_COMMAND_EVENT_CHAR_UUID,
            b"\x06" + code.encode("utf-8"),
            response=True,
        )

        print(f"[전송 완료] code={code}")

    print("YOLO 모델 로딩 중...")
    model = YOLO(MODEL_PATH)
    print("모델 클래스:", model.names)

    print("허브 검색 중...")
    device = await BleakScanner.find_device_by_name(HUB_NAME)

    if device is None:
        print(f"허브를 찾지 못했습니다: {HUB_NAME}")
        print("확인: Pybricks Code 연결 끊기, 허브 전원 켜기, HUB_NAME 확인")
        return

    print("허브 찾음:", device.name)

    async with BleakClient(device, disconnected_callback=handle_disconnect) as client:
        await client.start_notify(PYBRICKS_COMMAND_EVENT_CHAR_UUID, handle_rx)

        print("허브 가운데 버튼을 눌러 Pybricks 프로그램을 시작하세요.")
        print("허브에서 rdy 신호를 기다립니다...")

        await ready_event.wait()
        print("허브 준비 완료")

        print(f"카메라 여는 중... (source={VIDEO_SOURCE})")
        cap = open_camera(VIDEO_SOURCE)

        if cap is None:
            print("카메라를 열 수 없습니다. 확인 사항:")
            print("  1) iPhone 잠금 해제 + Mac과 같은 Apple ID + WiFi/Bluetooth ON (연속성 카메라)")
            print("  2) 카메라 권한: 시스템 설정 > 개인정보 보호 및 보안 > 카메라 에서")
            print("     실행 중인 앱(터미널/iTerm/VSCode) 허용 후 앱 재시작")
            print("  3) VIDEO_SOURCE 인덱스가 맞는지 find_camera.py로 확인")
            return

        # =========================
        # 전송 상태 변수
        # =========================

        d_sent_this_object = False
        class_sent_this_object = False

        object_start_time = None

        # 공 존재 안정화용
        object_seen_frames = 0

        # 불량 판정 누적 변수
        high_conf_detection_seen_this_object = False
        detection_color_this_object = None
        best_detection_conf_this_object = 0.0
        best_detection_label_this_object = None

        # 정상 판정 누적 변수
        best_normal_conf_this_object = 0.0
        best_normal_label_this_object = None

        # 색상 누적 변수
        object_color_this_object = None

        empty_count = 0
        required_empty_frames = 3

        # 폰 카메라(연속성 카메라)는 잠금/알림/전화 등으로 순간적으로 프레임이
        # 끊길 수 있다. 한 번 실패로 종료하지 않고 잠깐 재시도한다.
        read_fail_count = 0
        max_read_fail = 30

        print("실시간 탐지 시작. 종료하려면 q를 누르세요.")

        while True:
            ret, frame = cap.read()

            if not ret:
                read_fail_count += 1

                if read_fail_count == 1:
                    print("프레임 읽기 실패. 재시도 중... (iPhone 잠금/전화 여부 확인)")

                if read_fail_count >= max_read_fail:
                    print("프레임을 계속 읽지 못해 종료합니다.")
                    break

                await asyncio.sleep(0.1)
                continue

            read_fail_count = 0

            results = model.predict(frame, conf=YOLO_PREDICT_CONF, verbose=False)
            r = results[0]

            valid_boxes = get_valid_boxes(r)
            object_visible = len(valid_boxes) > 0

            detected_label = None
            detected_conf = 0.0
            detected_xyxy = None

            # =========================
            # 공 감지 안정화
            # =========================

            if object_visible:
                object_seen_frames += 1
                empty_count = 0

            else:
                object_seen_frames = 0
                empty_count += 1

            # =========================
            # 공이 연속 REQUIRED_OBJECT_FRAMES 프레임 이상 보이면 D모터 전송
            # =========================

            if (
                object_visible
                and not d_sent_this_object
                and object_seen_frames >= REQUIRED_OBJECT_FRAMES
            ):
                print(
                    f"[공 연속 {REQUIRED_OBJECT_FRAMES}프레임 감지 "
                    f"→ D모터 명령 전송 + {CLASSIFY_TIME:.1f}초 판정 시작]"
                )

                await send_code(client, "d")

                d_sent_this_object = True
                class_sent_this_object = False
                object_start_time = time.time()

                high_conf_detection_seen_this_object = False
                detection_color_this_object = None
                best_detection_conf_this_object = 0.0
                best_detection_label_this_object = None

                best_normal_conf_this_object = 0.0
                best_normal_label_this_object = None

                object_color_this_object = None

            # =========================
            # 박스 정보 확인 및 판정 누적
            # =========================

            best_box = None
            best_conf = -1

            if object_visible:
                for box in valid_boxes:
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    label = model.names[cls_id]
                    xyxy = box.xyxy[0].tolist()

                    if conf > best_conf:
                        best_conf = conf
                        best_box = box

                    each_color = get_color_from_label(label)

                    if each_color is None:
                        each_color = detect_color_from_bbox(frame, xyxy)

                    # 색상은 보조 정보로만 저장
                    if each_color is not None:
                        object_color_this_object = each_color

                    is_detection_label = (
                        "detection" in label
                        or label in NG_CLASSES
                    )

                    is_normal_label = (
                        "normal" in label
                        or label in OK_CLASSES
                    )

                    # D모터가 이미 돈 뒤에만 최종 판정용 점수 누적
                    if d_sent_this_object and not class_sent_this_object:
                        # detection 클래스 누적
                        if is_detection_label and conf >= DETECTION_CONF_THRESHOLD:
                            high_conf_detection_seen_this_object = True

                            if conf > best_detection_conf_this_object:
                                best_detection_conf_this_object = conf
                                best_detection_label_this_object = label

                                if each_color is not None:
                                    detection_color_this_object = each_color
                                    object_color_this_object = each_color

                        # normal 클래스 누적
                        if is_normal_label and conf > best_normal_conf_this_object:
                            best_normal_conf_this_object = conf
                            best_normal_label_this_object = label

                            label_color = get_color_from_label(label)
                            if label_color is not None:
                                object_color_this_object = label_color

                # =========================
                # 화면 표시용 best_box
                # =========================

                if best_box is not None:
                    cls_id = int(best_box.cls[0])
                    detected_label = model.names[cls_id]
                    detected_conf = float(best_box.conf[0])
                    detected_xyxy = best_box.xyxy[0].tolist()

                    x1, y1, x2, y2 = map(int, detected_xyxy)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(
                        frame,
                        f"{detected_label} {detected_conf:.2f}",
                        (x1, max(30, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2,
                    )

            # =========================
            # CLASSIFY_TIME이 지나면 최종 분류 코드 전송
            # =========================

            if (
                d_sent_this_object
                and not class_sent_this_object
                and object_start_time is not None
                and time.time() - object_start_time >= CLASSIFY_TIME
            ):
                # 1) detection이 한 번이라도 기준 이상이면 불량
                if high_conf_detection_seen_this_object:
                    final_color = detection_color_this_object or object_color_this_object
                    code = get_detection_code_by_color(final_color)

                    if code is not None:
                        print(
                            f"[최종 불량 전송] {CLASSIFY_TIME:.1f}초 동안 "
                            f"detection conf >= {DETECTION_CONF_THRESHOLD} 감지, "
                            f"detection_score={best_detection_conf_this_object:.2f}, "
                            f"detection_label={best_detection_label_this_object}, "
                            f"color={final_color}, 전송 코드={code}"
                        )

                        await send_code(client, code)
                        class_sent_this_object = True

                    else:
                        print(
                            f"[전송 보류] 불량으로 판단됐지만 color를 알 수 없음, "
                            f"detection_score={best_detection_conf_this_object:.2f}, "
                            f"detection_label={best_detection_label_this_object}"
                        )
                        class_sent_this_object = True

                # 2) detection이 아니면 normal 클래스가 실제로 잡혔을 때만 정상 전송
                else:
                    final_color = get_color_from_label(best_normal_label_this_object)

                    if final_color is None:
                        final_color = object_color_this_object

                    code = get_normal_code_by_color(final_color)

                    if (
                        best_normal_label_this_object is not None
                        and best_normal_conf_this_object >= NORMAL_CONF_THRESHOLD
                        and code is not None
                    ):
                        print(
                            f"[최종 정상 전송] {CLASSIFY_TIME:.1f}초 동안 "
                            f"detection conf >= {DETECTION_CONF_THRESHOLD} 없음, "
                            f"normal_score={best_normal_conf_this_object:.2f}, "
                            f"normal_label={best_normal_label_this_object}, "
                            f"color={final_color}, 전송 코드={code}"
                        )

                        await send_code(client, code)
                        class_sent_this_object = True

                    else:
                        print(
                            f"[전송 보류] detection도 아니고 normal도 확실하지 않음, "
                            f"normal_score={best_normal_conf_this_object:.2f}, "
                            f"normal_label={best_normal_label_this_object}, "
                            f"color={final_color}"
                        )

                        # 같은 공에 대해 계속 전송 시도하지 않도록 이번 공은 종료 처리
                        class_sent_this_object = True

            # =========================
            # 공이 사라졌을 때 다음 공 준비
            # =========================

            if not object_visible:
                if empty_count >= required_empty_frames and class_sent_this_object:
                    d_sent_this_object = False
                    class_sent_this_object = False

                    object_start_time = None
                    object_seen_frames = 0

                    high_conf_detection_seen_this_object = False
                    detection_color_this_object = None
                    best_detection_conf_this_object = 0.0
                    best_detection_label_this_object = None

                    best_normal_conf_this_object = 0.0
                    best_normal_label_this_object = None

                    object_color_this_object = None

            # =========================
            # 화면 표시
            # =========================

            elapsed = 0.0
            if object_start_time is not None and not class_sent_this_object:
                elapsed = time.time() - object_start_time

            cv2.putText(
                frame,
                (
                    f"seen_frames: {object_seen_frames}, "
                    f"elapsed: {elapsed:.2f}/{CLASSIFY_TIME:.2f}s, "
                    f"class_sent: {class_sent_this_object}"
                ),
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
            )

            cv2.putText(
                frame,
                (
                    f"defect_seen: {high_conf_detection_seen_this_object}, "
                    f"normal_score: {best_normal_conf_this_object:.2f}"
                ),
                (20, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
            )

            if object_color_this_object is not None:
                cv2.putText(
                    frame,
                    f"color: {object_color_this_object}",
                    (20, 95),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                )

            cv2.imshow("YOLO to SPIKE", frame)

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