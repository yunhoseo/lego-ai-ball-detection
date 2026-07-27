# 레고 AI 공 탐지 실습 (고색고)

**"공을 보여주면 모터가 돈다"** — 스마트폰 카메라 + YOLO 객체탐지 + LEGO SPIKE Prime을 연결하는 AI 실습 자료입니다.

```
스마트폰 카메라 ──WiFi(Iriun)──▶ 노트북 (YOLO 공 탐지) ──블루투스(BLE)──▶ SPIKE 허브 ──▶ 모터 1회전
     (눈)                              (두뇌)                                  (손)
```

- 시연 영상: [`demo.mp4`](demo.mp4)
- 학생용 단계별 안내서(설치·연결·문제해결 전체 수록): [`guide.html`](guide.html) — 다운로드 후 브라우저로 열기

## 준비물

- Windows 노트북(블루투스 지원) + Chrome/Edge
- 스마트폰(Iriun Webcam 앱으로 무선 카메라화, 노트북과 같은 WiFi)
- LEGO SPIKE Prime 허브 + 모터 1개 + USB 데이터 케이블
- 허브 펌웨어: [Pybricks](https://code.pybricks.com) (허브당 최초 1회 설치)

```bash
pip install -r requirements.txt   # ultralytics, opencv-python, bleak
```

## 파일 구성

### 노트북에서 실행하는 코드 (PC용)

| 파일 | 역할 |
|---|---|
| `baseline_1_camera.py` | 연습 1 — 폰 카메라 화면을 노트북 창에 띄우기 (`VIDEO_SOURCE` 번호 확인) |
| `baseline_2_vision.py` | 연습 2 — YOLO로 공 탐지, 초록 상자+라벨 표시 (모터 없이 확인) |
| `baseline_3_motor.py` | 연습 3 — 탐지 시 허브 A모터 1회전 (최종 목표, 학생용 축약판) |
| `detect_spin_a.py` | 본편 — 연습 3과 동일 흐름 + 재시도·중복 트리거 방지 등 안전장치 포함 |
| `detect_only.py` | 허브 없이 카메라+YOLO 탐지만 확인하는 뷰어 |
| `balldetection_1.py` | 심화 — 색상(빨강/파랑/초록)·양불(normal/detection) 분류 → 모터 5개 분류기 구동 |
| `find_camera.py` | 카메라 인덱스 찾기 도우미 |
| `test_zoom.py` | 카메라 zoom(CAP_PROP_ZOOM) 지원 여부 테스트 |

### 허브에 넣는 코드 (Pybricks용 — code.pybricks.com에서 붙여넣어 실행)

| 파일 | 역할 | 짝이 되는 PC 코드 |
|---|---|---|
| `spike_hub_a_once.py` | A모터 1개, "d" 수신 시 1회전 | `baseline_3_motor.py`, `detect_spin_a.py` |
| `spike_hub.py` | 모터 5개(컨베이어·분기·분리) 색상 분류 동작 | `balldetection_1.py` |
| `spike_hub_test.py` | 모터 5개 배선/동작 확인용 스캐폴드 | — |

### 모델

- `best.pt` — 공 탐지 YOLO 모델 (6MB). 클래스: `red/blue/green_normal`, `red/blue/green_detection`(불량). 모든 PC 코드가 같은 폴더의 `best.pt`를 읽습니다.

## 실행 순서 (순서가 생명!)

1. **Pybricks 브라우저 탭을 완전히 닫는다** — 탭이 열려 있으면 허브를 독차지해서 PC 프로그램이 연결 못 함.
2. 허브를 **파란 깜빡임**(연결 대기) 상태로 둔다.
3. Iriun 실행(폰 앱 + 노트북 프로그램), 폰 화면이 노트북에 보이는지 확인.
4. `python detect_spin_a.py` 실행 → "허브 찾음" → 카메라 창이 뜰 때까지 대기.
5. 카메라 창이 뜨면 **허브 가운데 버튼을 눌러 초록불**(프로그램 실행)로 만든다.
6. 공을 카메라에 보여주면 모터가 한 바퀴 돈다. 치웠다 다시 보여주면 또 돈다.
7. 종료: 카메라 창 클릭 후 `q` (허브도 자동 정리, 빨간불).

### 허브 불빛 = 신호등

| 불빛 | 상태 |
|---|---|
| 파란 깜빡임 | 연결 대기 — 노트북이 허브를 찾을 수 있는 **유일한** 상태 |
| 초록 | 프로그램 실행 중 — 모터 신호 수신 가능 (새 연결은 불가) |
| 빨강 | 프로그램 종료 — 가운데 버튼으로 재시작 |

## 자주 막히는 곳

- **허브를 못 찾음** → Pybricks 탭 닫았는지, 허브가 파란 깜빡임인지 확인.
- **카메라가 안 열림 / 노트북 내장캠이 나옴** → `find_camera.py`로 인덱스 확인 후 각 스크립트의 `VIDEO_SOURCE` 수정.
- **`A NOT FOUND`** → 모터 케이블이 허브 **A 포트**에 안 꽂힘.
- **학교 WiFi에서 Iriun 연결 안 됨** → 기기 간 통신 차단 때문. 폰 핫스팟을 켜고 노트북을 핫스팟에 연결.
- **공이 잘 안 잡힘** → 스크립트의 `CONF`를 0.5 → 0.3으로 낮춰서 시도.

## 통신 방식 (요약)

PC는 `bleak`로 허브의 Pybricks BLE 특성(`c5f50002-...`)에 1바이트 명령을 씁니다. 공이 연속 3프레임 감지되면 `"d"` 전송 → 허브의 `spike_hub_a_once.py`가 `stdin`으로 받아 A모터를 360° 회전 → `rdy` 응답. 공이 사라져 3프레임 비면 다시 무장(재트리거 가능) — 공 하나당 한 번만 돌게 하는 장치입니다.
