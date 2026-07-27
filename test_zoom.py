"""
CAP_PROP_ZOOM 동작 테스트 (macOS 연속성 카메라).

카메라를 열고 +/- 키로 zoom 값을 바꿔가며 화면이 실제로 변하는지 확인한다.
- 화면이 바뀌면: OpenCV zoom이 먹힌다 → 원하는 값을 balldetection_1.py CAM_ZOOM에 넣으면 됨.
- 아무 변화 없으면: 이 맥/카메라 조합에선 zoom 미지원 → 물리적으로 폰을 뒤로 빼야 함.

사용법:
    python test_zoom.py          # 기본 index 1 (iPhone)
    python test_zoom.py 0        # 다른 인덱스 지정

조작:
    + / =  → zoom 값 올리기
    -      → zoom 값 내리기
    r      → 1.0 으로 리셋
    q      → 종료
"""

import sys
import cv2

INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else 1
STEP = 0.5


def make_cap(idx):
    if sys.platform == "darwin":
        return cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
    return cv2.VideoCapture(idx)


def main():
    cap = make_cap(INDEX)
    if not cap.isOpened():
        print(f"index {INDEX} 를 열 수 없습니다.")
        return

    for _ in range(10):
        cap.read()

    initial = cap.get(cv2.CAP_PROP_ZOOM)
    print(f"index {INDEX} 열림. 초기 CAP_PROP_ZOOM(get) = {initial}")
    print("+/= 올리기, - 내리기, r 리셋, q 종료")

    zoom = 1.0

    while True:
        ok, frame = cap.read()
        if not ok:
            print("프레임 읽기 실패")
            break

        read_back = cap.get(cv2.CAP_PROP_ZOOM)

        cv2.putText(
            frame,
            f"set_zoom={zoom:.2f}  read_back(get)={read_back:.2f}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            frame,
            "(+/- change, r reset, q quit)",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
        cv2.imshow("test_zoom", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        changed = False
        if key in (ord("+"), ord("=")):
            zoom += STEP
            changed = True
        elif key == ord("-"):
            zoom = max(0.0, zoom - STEP)
            changed = True
        elif key == ord("r"):
            zoom = 1.0
            changed = True

        if changed:
            ret = cap.set(cv2.CAP_PROP_ZOOM, zoom)
            new_get = cap.get(cv2.CAP_PROP_ZOOM)
            print(f"set(CAP_PROP_ZOOM, {zoom:.2f}) -> 반환 {ret}, get={new_get:.2f}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
