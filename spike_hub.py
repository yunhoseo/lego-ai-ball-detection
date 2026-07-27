# =====================================================================
# SPIKE 허브 프로그램 (Pybricks) — 실제 분류 동작
# =====================================================================
# Mac이 아니라 "허브"에서 돕니다.
#   code.pybricks.com 접속 → 허브 연결 → 붙여넣기 → Download →
#   Pybricks Code 연결 끊기 → Mac에서 balldetection_1.py 실행 →
#   허브 가운데 버튼 눌러 시작.
#
# 모터 배치:
#   A 컨베이어(연속) / B 초록·파랑 분류 / C 크랭크(연속) /
#   E 메인 색상 분기(빨강 ↔ 파랑·초록) / F 빨강 불량 분리
#
# 동작 설계:
#   - A, C : 시작하면 계속 회전 (공 연속 공급)
#   - E : 빨강 라인 / 파랑·초록 라인 으로 분기
#   - B : 파랑 / 초록 / (파랑·초록 불량) 위치로
#   - F : 빨강 불량이면 밀어냈다 복귀, 정상이면 통과
#
# ★ 아래 [튜닝] 각도/속도는 실물 보고 맞추세요. 부호(+/-)로 방향 바뀝니다.
#   시작 전 E·B·F 를 "기본 위치"(빨강 / 파랑 / 통과)에 두고 켜세요 → 그 지점이 0.
# =====================================================================

from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port, Color
from pybricks.tools import wait

from usys import stdin, stdout
from uselect import poll

hub = PrimeHub()

# ---------------------------------------------------------------------
# 포트 (배선 바뀌면 여기만)
# ---------------------------------------------------------------------
PORT_CONVEYOR = Port.A
PORT_SORT_GB = Port.B
PORT_CRANK = Port.C
PORT_SORT = Port.E
PORT_RED_NG = Port.F

# ---------------------------------------------------------------------
# [튜닝] 속도 · 각도
# ---------------------------------------------------------------------
CONVEYOR_SPEED = 500      # 컨베이어 연속 속도 (deg/s, 부호=방향)
CRANK_SPEED = 300         # 크랭크 연속 속도

MOVE_SPEED = 500          # 다이버터 이동 속도

# 공 감지(d) 즉시 반응용 크랭크 킥 (연속 회전에 얹어서 순간적으로 더 돌림)
DETECT_KICK_SPEED = 500
DETECT_KICK_ANGLE = 360

# E: 메인 색상 분기 (기본 위치 = 빨강 = 0)
E_RED = 0
E_BLUEGREEN = 90

# B: 파랑·초록 분류 (기본 위치 = 파랑 = 0)
B_BLUE = 0
B_GREEN = 90
B_NG = -90                # 파랑·초록 불량 위치

# F: 빨강 불량 분리 (기본 위치 = 통과 = 0)
F_PASS = 0
F_SEPARATE = 90
F_HOLD_MS = 400           # 불량 밀어낸 뒤 유지 시간


def try_motor(port, name):
    try:
        m = Motor(port)
        print(name, "OK")
        return m
    except Exception:
        print(name, "NOT FOUND")
        return None


def run_cont(m, speed):
    if m is not None:
        m.run(speed)


def to_angle(m, angle):
    if m is not None:
        m.run_target(MOVE_SPEED, angle)


def stop_m(m):
    if m is not None:
        m.stop()


def kick(m, speed, angle):
    """연속 회전 중인 모터를 순간적으로 더 돌려 '방금 감지됨'을 눈으로 확인시킨다."""
    if m is not None:
        m.run_angle(speed, angle)


def send(msg):
    stdout.buffer.write(msg)


keyboard = poll()
keyboard.register(stdin)

# ---------------------------------------------------------------------
# 모터 잡기
# ---------------------------------------------------------------------
print("motors init...")
CONVEYOR = try_motor(PORT_CONVEYOR, "A conveyor")
SORT_GB = try_motor(PORT_SORT_GB, "B green/blue")
CRANK = try_motor(PORT_CRANK, "C crank")
SORT = try_motor(PORT_SORT, "E main-split")
RED_NG = try_motor(PORT_RED_NG, "F red-NG")

# 다이버터 기준점(0) 설정 — 지금 위치를 기본 위치로 삼음
for m in (SORT, SORT_GB, RED_NG):
    if m is not None:
        m.reset_angle(0)

# 컨베이어 · 크랭크 연속 회전 시작
run_cont(CONVEYOR, CONVEYOR_SPEED)
run_cont(CRANK, CRANK_SPEED)


# ---------------------------------------------------------------------
# 코드 → 분류 동작
# ---------------------------------------------------------------------
def route(cmd):
    if cmd == b"d":
        # 감지 즉시 크랭크를 한 번 더 돌려 반응을 보여준 뒤 연속 회전 복귀
        hub.display.char("d")
        kick(CRANK, DETECT_KICK_SPEED, DETECT_KICK_ANGLE)
        run_cont(CRANK, CRANK_SPEED)
        return

    if cmd == b"0":            # red_normal → 빨강 라인, 통과
        hub.display.number(0)
        to_angle(SORT, E_RED)
        to_angle(RED_NG, F_PASS)

    elif cmd == b"1":          # red_detection → 빨강 라인, 불량 밀어냄
        hub.display.number(1)
        to_angle(SORT, E_RED)
        to_angle(RED_NG, F_SEPARATE)
        wait(F_HOLD_MS)
        to_angle(RED_NG, F_PASS)

    elif cmd == b"2":          # blue_normal → 파랑·초록 라인, 파랑
        hub.display.number(2)
        to_angle(SORT, E_BLUEGREEN)
        to_angle(SORT_GB, B_BLUE)

    elif cmd == b"3":          # blue_detection → 라인, 불량 위치
        hub.display.number(3)
        to_angle(SORT, E_BLUEGREEN)
        to_angle(SORT_GB, B_NG)

    elif cmd == b"4":          # green_normal → 라인, 초록
        hub.display.number(4)
        to_angle(SORT, E_BLUEGREEN)
        to_angle(SORT_GB, B_GREEN)

    elif cmd == b"5":          # green_detection → 라인, 불량 위치
        hub.display.number(5)
        to_angle(SORT, E_BLUEGREEN)
        to_angle(SORT_GB, B_NG)


# ---------------------------------------------------------------------
# 메인 통신 루프 (rdy 핸드셰이크)
# ---------------------------------------------------------------------
hub.light.on(Color.GREEN)
send(b"rdy")

while True:
    if keyboard.poll(0):
        cmd = stdin.buffer.read(1)
        if not cmd:
            continue
        if cmd == b"q":
            break
        route(cmd)
        send(b"rdy")
    else:
        wait(10)

# 종료 정리
stop_m(CONVEYOR)
stop_m(CRANK)
hub.light.on(Color.RED)
hub.display.off()
