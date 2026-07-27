# =====================================================================
# SPIKE 허브 프로그램 (Pybricks) — A모터 전용, "탐지되면 1회전"만 테스트
# =====================================================================
# Mac이 아니라 "허브"에서 돕니다.
#   code.pybricks.com 접속 → 허브 연결 → 붙여넣기 → Download →
#   Pybricks Code 연결 끊기 → Mac에서 detect_spin_a.py 실행 →
#   허브 가운데 버튼 눌러 시작.
#
# Mac이 공을 감지할 때마다 "d"를 보내고, 허브는 A 모터를 SPIN_ANGLE만큼
# (기본 360도 = 1회전) 돌린 뒤 다음 감지를 기다린다. 그 외 동작 없음
# (색상 분류·컨베이어 상시 회전 없음 — spike_hub.py와 다름).
# =====================================================================

from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port, Color
from pybricks.tools import wait

from usys import stdin, stdout
from uselect import poll

hub = PrimeHub()

PORT_A = Port.A

SPIN_SPEED = 500   # deg/s
SPIN_ANGLE = 360    # 1회전


def try_motor(port, name):
    try:
        m = Motor(port)
        print(name, "OK")
        return m
    except Exception:
        print(name, "NOT FOUND")
        return None


def send(msg):
    stdout.buffer.write(msg)


A = try_motor(PORT_A, "A")

keyboard = poll()
keyboard.register(stdin)

hub.light.on(Color.GREEN)
send(b"rdy")

while True:
    if keyboard.poll(0):
        cmd = stdin.buffer.read(1)
        if not cmd:
            continue

        if cmd == b"q":
            break

        if cmd == b"d":
            hub.display.char("d")
            if A is not None:
                A.run_angle(SPIN_SPEED, SPIN_ANGLE)

        send(b"rdy")
    else:
        wait(10)

if A is not None:
    A.stop()
hub.light.on(Color.RED)
hub.display.off()
