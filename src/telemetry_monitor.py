"""实时打印进站修复耗时。
通过车损原始值估算，直接读取 ACC 共享内存。
"""

import ctypes
import mmap
import time
import sys


class SPageFilePhysics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('packetId', ctypes.c_int),
        ('gas', ctypes.c_float),
        ('brake', ctypes.c_float),
        ('fuel', ctypes.c_float),
        ('gear', ctypes.c_int),
        ('rpms', ctypes.c_int),
        ('steerAngle', ctypes.c_float),
        ('speedKmh', ctypes.c_float),
        ('velocity', ctypes.c_float * 3),
        ('accG', ctypes.c_float * 3),
        ('wheelSlip', ctypes.c_float * 4),
        ('wheelLoad', ctypes.c_float * 4),
        ('wheelsPressure', ctypes.c_float * 4),
        ('wheelAngularSpeed', ctypes.c_float * 4),
        ('tyreWear', ctypes.c_float * 4),
        ('tyreDirtyLevel', ctypes.c_float * 4),
        ('tyreCoreTemperature', ctypes.c_float * 4),
        ('camberRAD', ctypes.c_float * 4),
        ('suspensionTravel', ctypes.c_float * 4),
        ('drs', ctypes.c_float),
        ('tc', ctypes.c_float),
        ('heading', ctypes.c_float),
        ('pitch', ctypes.c_float),
        ('roll', ctypes.c_float),
        ('cgHeight', ctypes.c_float),
        ('carDamage', ctypes.c_float * 5),
        ('numberOfTyresOut', ctypes.c_int),
        ('pitLimiterOn', ctypes.c_int),
        ('abs', ctypes.c_float),
        ('kersCharge', ctypes.c_float),
        ('kersInput', ctypes.c_float),
        ('autoShifterOn', ctypes.c_int),
        ('rideHeight', ctypes.c_float * 2),
        ('turboBoost', ctypes.c_float),
        ('ballast', ctypes.c_float),
        ('airDensity', ctypes.c_float),
        ('airTemp', ctypes.c_float),
        ('roadTemp', ctypes.c_float),
        ('localAngularVel', ctypes.c_float * 3),
        ('finalFF', ctypes.c_float),
        ('performanceMeter', ctypes.c_float),
        ('engineBrake', ctypes.c_int),
        ('ersRecoveryLevel', ctypes.c_int),
        ('ersPowerLevel', ctypes.c_int),
        ('ersHeatCharging', ctypes.c_int),
        ('ersIsCharging', ctypes.c_int),
        ('kersCurrentKJ', ctypes.c_float),
        ('drsAvailable', ctypes.c_int),
        ('drsEnabled', ctypes.c_int),
        ('brakeTemp', ctypes.c_float * 4),
        ('clutch', ctypes.c_float),
        ('tyreTempI', ctypes.c_float * 4),
        ('tyreTempM', ctypes.c_float * 4),
        ('tyreTempO', ctypes.c_float * 4),
        ('isAIControlled', ctypes.c_int),
        ('tyreContactPoint', (ctypes.c_float * 3) * 4),
        ('tyreContactNormal', (ctypes.c_float * 3) * 4),
        ('tyreContactHeading', (ctypes.c_float * 3) * 4),
        ('brakeBias', ctypes.c_float),
        ('localVelocity', ctypes.c_float * 3),
        ('P2PActivations', ctypes.c_int),
        ('P2PStatus', ctypes.c_int),
        ('currentMaxRpm', ctypes.c_float),
        ('mz', ctypes.c_float * 4),
        ('fx', ctypes.c_float * 4),
        ('fy', ctypes.c_float * 4),
        ('slipRatio', ctypes.c_float * 4),
        ('slipAngle', ctypes.c_float * 4),
        ('tcinAction', ctypes.c_int),
        ('absInAction', ctypes.c_int),
        ('suspensionDamage', ctypes.c_float * 4),
        ('tyreTemp', ctypes.c_float * 4),
        ('waterTemp', ctypes.c_float),
        ('brakePressure', ctypes.c_float * 4),
        ('frontBrakeCompound', ctypes.c_int),
        ('rearBrakeCompound', ctypes.c_int),
        ('padLife', ctypes.c_float * 4),
        ('discLife', ctypes.c_float * 4),
        ('ignitionOn', ctypes.c_int),
        ('starterEngineOn', ctypes.c_int),
        ('isEngineRunning', ctypes.c_int),
        ('kerbVibration', ctypes.c_float),
        ('slipVibrations', ctypes.c_float),
        ('gVibrations', ctypes.c_float),
        ('absVibrations', ctypes.c_float),
    ]


def open_shm():
    """尝试打开共享内存，失败返回 None"""
    for name in ("acpmf_physics", "Local\\acpmf_physics"):
        try:
            return mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), name, access=mmap.ACCESS_READ)
        except FileNotFoundError:
            continue
    return None


DAMAGE_SCALE = 7.08  # 车损→修复秒数换算系数（实测拟合）

def main():
    print("ACC 进站耗时监控（估算）")
    print("等待 ACC 游戏…")

    shm = None
    prev_packet = -1

    while True:
        if shm is None:
            shm = open_shm()
            if shm is None:
                time.sleep(1)
                continue
            print("已连接 ACC 共享内存")

        try:
            shm.seek(0)
            buf = shm.read(ctypes.sizeof(SPageFilePhysics))
            data = SPageFilePhysics.from_buffer_copy(buf)
        except OSError:
            print("共享内存读取失败，尝试重连…")
            shm = None
            time.sleep(1)
            continue

        if data.packetId == prev_packet:
            time.sleep(0.05)
            continue
        prev_packet = data.packetId

        total_raw = sum(data.carDamage[:5])
        repair_sec = total_raw / DAMAGE_SCALE

        bar = "█" * int(min(repair_sec, 20)) + "░" * (20 - int(min(repair_sec, 20)))
        print(f"修复耗时: {repair_sec:>5.1f}s  {bar}")

        time.sleep(0.2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已退出")
        sys.exit(0)
