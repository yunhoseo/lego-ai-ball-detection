# =====================================================================
# SPIKE 허브 프로그램 (Pybricks) — 모터 5개 배선/동작 확인 스캐폴드
# =====================================================================
# 이 코드는 Mac이 아니라 "허브"에서 돕니다.
#   실행법: https://code.pybricks.com  접속 → 허브 연결 →
#           이 코드 붙여넣기 → Download →
#           Pybricks Code 연결 끊기 → Mac에서 balldetection_1.py 실행 →
#           허브 가운데 버튼 눌러 이 프로그램 시작.
#
# 모터 배치 (사용자 실제 구성):
#   A 컨베이어 벨트 / B 초록·파랑 분류 / C 크랭크 / E 분류 모터 / F 빨강 불량 분리
#
# PC가 보내는 코드:
#   d  공 감지          0 red_normal   1 red_detection(빨강 불량)
#                      2 blue_normal  3 blue_detection(파랑 불량)
#                      4 green_normal 5 green_detection(초록 불량)
#   q  종료
#
# 지금은 "테스트" 버전 — 각 코드마다 관련 모터를 살짝 wiggle 해서
# 통신·모터·배선이 맞는지 확인만 한다. 실제 각도/방향은 handle()에서 조정.
# =====================================================================

from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port, Color
from pybricks.tools import wait

from usys import stdin, stdout
from uselect import poll

hub = PrimeHub()

# ---------------------------------------------------------------------
# 모터 포트 설정  (배선 바뀌면 여기만 수정)
# ---------------------------------------------------------------------
PORT_CONVEYOR = Port.A   # 컨베이어 벨트
PORT_SORT_GB = Port.B    # 초록/파랑 분류
PORT_CRANK = Port.C      # 크랭크
PORT_SORT = Port.E       # 분류 모터
PORT_RED_NG = Port.F     # 빨강 불량 분리

WIGGLE_SPEED = 400       # deg/s
WIGGLE_ANGLE = 120       # 테스트로 움직일 각도


def try_motor(port, name):
    """포트에 모터가 있으면 잡고, 없으면 None (프로그램은 계속 진행)."""
    try:
        m = Motor(port)
        print(name, "OK")
        return m
    except Exception:
        print(name, "NOT FOUND")
        return None


def wiggle(m):
    """앞뒤로 살짝 움직여 신호를 확인 (원위치 복귀)."""
    if m is None:
        return
    m.run_angle(WIGGLE_SPEED, WIGGLE_ANGLE)
    m.run_angle(WIGGLE_SPEED, -WIGGLE_ANGLE)


def send(msg):
    stdout.buffer.write(msg)


keyboard = poll()
keyboard.register(stdin)

# ---------------------------------------------------------------------
# 모터 잡기 + 시작 자가 테스트 (A→B→C→E→F 순서로 꿈틀 → 배선 확인)
# ---------------------------------------------------------------------
print("motors init...")
CONVEYOR = try_motor(PORT_CONVEYOR, "A conveyor")
SORT_GB = try_motor(PORT_SORT_GB, "B green/blue")
CRANK = try_motor(PORT_CRANK, "C crank")
SORT = try_motor(PORT_SORT, "E sorter")
RED_NG = try_motor(PORT_RED_NG, "F red-NG")

for label, m in (("A", CONVEYOR), ("b", SORT_GB), ("C", CRANK),
                 ("E", SORT), ("F", RED_NG)):
    if m is not None:
        hub.display.char(label)
        wiggle(m)
        wait(150)
hub.display.off()


# ---------------------------------------------------------------------
# 코드 → 모터 동작  (지금은 테스트 wiggle, 실제 분류는 여기서 채움)
#   ※ TODO 표시된 부분은 실제 안무가 정해지면 바꾸세요.
# ---------------------------------------------------------------------
def handle(cmd):
    if cmd == b"d":            # 공 감지 → 분류 위치로 이동
        hub.display.char("d")
        wiggle(CONVEYOR)       # TODO: 컨베이어 전진 / 크랭크로 밀기 등
        wiggle(CRANK)

    elif cmd == b"0":          # red_normal (빨강 정상)
        hub.display.number(0)
        wiggle(SORT)           # TODO: 빨강 정상 경로

    elif cmd == b"1":          # red_detection (빨강 불량)
        hub.display.number(1)
        wiggle(RED_NG)         # F: 빨강 불량 분리

    elif cmd == b"2":          # blue_normal
        hub.display.number(2)
        wiggle(SORT_GB)        # B: 파랑 방향

    elif cmd == b"3":          # blue_detection (파랑 불량)
        hub.display.number(3)
        wiggle(SORT_GB)        # TODO: 파랑 불량 처리 (전용 모터 없음)

    elif cmd == b"4":          # green_normal
        hub.display.number(4)
        wiggle(SORT_GB)        # B: 초록 방향

    elif cmd == b"5":          # green_detection (초록 불량)
        hub.display.number(5)
        wiggle(SORT_GB)        # TODO: 초록 불량 처리 (전용 모터 없음)


# ---------------------------------------------------------------------
# 메인 통신 루프 (rdy 핸드셰이크)
# ---------------------------------------------------------------------
hub.light.on(Color.GREEN)
send(b"rdy")                    # PC에게 준비 완료 알림

while True:
    if keyboard.poll(0):
        cmd = stdin.buffer.read(1)
        if not cmd:
            continue
        if cmd == b"q":         # 종료
            break
        handle(cmd)
        send(b"rdy")            # 처리 끝, 다음 코드 받을 준비
    else:
        wait(10)

hub.light.on(Color.RED)
hub.display.off()
