"""Эмулятор робота: шлёт телеметрию в бэкенд по тому же gRPC-протоколу,
что и нода grpc_bridge. Нужен, чтобы разрабатывать фронт без ROS и симулятора.

    python scripts/fake_robot.py --robot-id robot_v1_simulation
    python scripts/fake_robot.py --robots 3 --batch-interval 1 --duration 60
"""

import argparse
import math
import random
import sys
import threading
import time
from pathlib import Path

import grpc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.grpc_gen import telemetry_pb2, telemetry_pb2_grpc  # noqa: E402

OK = telemetry_pb2.TelemetryStatus.Value("OK")
NOTF = telemetry_pb2.TelemetryStatus.Value("NOTF")


class SimRobot:
    """Робот едет по «восьмёрке», одометрия догоняет команду с задержкой и шумом."""

    def __init__(self, seed: int, notf_prob: float):
        self.rng = random.Random(seed)
        self.x = self.rng.uniform(-1, 1)
        self.y = self.rng.uniform(-1, 1)
        self.yaw = self.rng.uniform(-math.pi, math.pi)
        self.odom_v = 0.0
        self.odom_w = 0.0
        self.t = 0.0
        self.notf_left = 0
        self.notf_prob = notf_prob

    def step(self, dt: float) -> telemetry_pb2.TelemetryPoint:
        self.t += dt
        # иногда стоим, иначе едем
        moving = (self.t % 40) < 34
        cmd_v = 0.25 if moving else 0.0
        cmd_w = 0.6 * math.sin(self.t / 4) if moving else 0.0

        # инерция + шум
        alpha = 0.15
        self.odom_v += alpha * (cmd_v - self.odom_v) + self.rng.gauss(0, 0.005)
        self.odom_w += alpha * (cmd_w - self.odom_w) + self.rng.gauss(0, 0.01)

        self.yaw = math.atan2(math.sin(self.yaw + self.odom_w * dt), math.cos(self.yaw + self.odom_w * dt))
        self.x += self.odom_v * math.cos(self.yaw) * dt
        self.y += self.odom_v * math.sin(self.yaw) * dt

        point = telemetry_pb2.TelemetryPoint(
            timestamp_ms=int(time.time() * 1000),
            cmd_vel=telemetry_pb2.MotionTwist(linear_x=cmd_v, angular_z=cmd_w),
            odom_vel=telemetry_pb2.MotionTwist(linear_x=self.odom_v, angular_z=self.odom_w),
        )

        if self.notf_left == 0 and self.rng.random() < self.notf_prob:
            self.notf_left = self.rng.randint(5, 40)
        if self.notf_left > 0:
            self.notf_left -= 1
            point.status = NOTF
            point.status_message = '"map" passed to lookupTransform argument target_frame does not exist.'
        else:
            point.status = OK
            point.pose.CopyFrom(telemetry_pb2.RobotPose(x=self.x, y=self.y, yaw=self.yaw))
        return point


def run_robot(robot_id: str, args, seed: int, stop: threading.Event) -> None:
    channel = grpc.insecure_channel(args.target)
    stub = telemetry_pb2_grpc.TelemetryServiceStub(channel)
    robot = SimRobot(seed, args.notf_prob)
    dt = 1.0 / args.rate
    buffer: list[telemetry_pb2.TelemetryPoint] = []
    last_send = time.monotonic()

    while not stop.is_set():
        buffer.append(robot.step(dt))
        if time.monotonic() - last_send >= args.batch_interval:
            request = telemetry_pb2.TelemetryBatchRequest(robot_id=robot_id, points=buffer)
            try:
                stub.SendTelemetryBatch(request, timeout=5)
                print(f"[{robot_id}] отправлено {len(buffer)} точек")
                buffer = []
            except grpc.RpcError as e:
                # как и нода — копим точки и пробуем в следующий раз
                print(f"[{robot_id}] ошибка отправки: {e.code().name} {e.details()}")
            last_send = time.monotonic()
        time.sleep(dt)
    channel.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", default="localhost:50051", help="адрес gRPC-сервера бэкенда")
    parser.add_argument("--robot-id", default="robot_v1_simulation")
    parser.add_argument("--robots", type=int, default=1, help="сколько роботов эмулировать")
    parser.add_argument("--rate", type=float, default=20.0, help="частота точек, Гц (у ноды 20)")
    parser.add_argument("--batch-interval", type=float, default=5.0, help="период отправки, с (у ноды 5)")
    parser.add_argument("--notf-prob", type=float, default=0.002, help="вероятность потери TF на шаге")
    parser.add_argument("--duration", type=float, default=0, help="сколько секунд работать (0 — бесконечно)")
    args = parser.parse_args()

    ids = [args.robot_id] if args.robots == 1 else [f"{args.robot_id}_{i + 1}" for i in range(args.robots)]
    stop = threading.Event()
    threads = [
        threading.Thread(target=run_robot, args=(rid, args, i, stop), daemon=True) for i, rid in enumerate(ids)
    ]
    for t in threads:
        t.start()
    try:
        if args.duration > 0:
            time.sleep(args.duration)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    stop.set()
    for t in threads:
        t.join(timeout=args.batch_interval + 6)


if __name__ == "__main__":
    main()
