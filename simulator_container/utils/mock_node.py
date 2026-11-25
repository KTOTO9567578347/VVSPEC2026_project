import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster
import random

class MockRobotNode(Node):
    def __init__(self):
        super().__init__('mock_robot_1_sim')

        # Параметр режима: 'normal', 'wandering', 'slippage'
        self.declare_parameter('mode', 'normal')
        self.declare_parameter('rate', 20.0)  # Гц

        self.rate = self.get_parameter('rate').value
        self.dt = 1.0 / self.rate

        # Паблишеры топиков из вашего конфига
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # Бродкастер TF (map -> base_link)
        self.tf_broadcaster = TransformBroadcaster(self)

        # Состояние робота
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.t = 0.0

        self.timer = self.create_timer(self.dt, self.timer_callback)
        self.get_logger().info('Mock-нода для robot_1_sim запущена.')

    def timer_callback(self):
        mode = self.get_parameter('mode').get_parameter_value().string_value
        self.t += self.dt
        now = self.get_clock().now().to_msg()

        # 1. Формируем управляющее воздействие (cmd_vel) и реальную скорость (odom)
        cmd = Twist()
        real_v = 0.0
        real_w = 0.0

        # Внутри timer_callback:
        if mode == 'normal':
            # Цикл 16 секунд: 6 сек едем прямо -> 2 сек плавный поворот на 90° -> повторяем (движение по квадрату/рядам)
            cycle_t = self.t % 16.0
            if cycle_t < 6.0:
                # Прямой участок с плавным разгоном/торможением (хорошо для обучения регрессии)
                cmd.linear.x = 0.5 + 0.15 * math.sin(cycle_t * math.pi / 6.0)
                cmd.angular.z = 0.0
            elif cycle_t < 8.0:
                # Поворот на ~90 градусов (pi/2 рад за 2 сек ≈ 0.785 рад/с)
                cmd.linear.x = 0.15
                cmd.angular.z = math.pi / 4.0
            elif cycle_t < 14.0:
                # Следующий прямой участок с другой скоростью
                cmd.linear.x = 0.45
                cmd.angular.z = 0.0
            else:
                # Поворот в другую сторону (змейка по проходам склада)
                cmd.linear.x = 0.15
                cmd.angular.z = -math.pi / 4.0
    
            # В норме одометрия честно повторяет команду с минимальным шумом
            real_v = cmd.linear.x + random.gauss(0.0, 0.01)
            real_w = cmd.angular.z + random.gauss(0.0, 0.01)
    
        elif mode == 'anomaly':
            # Нецелевое поведение: робот пытается ехать по маршруту, но его сносит и крутит петлями на месте
            cmd.linear.x = 0.55
            cmd.angular.z = 0.1 * math.sin(self.t)
    
            # Сильное расхождение скоростей (высокий RMSE) + закручивание в петли на карте
            real_v = 0.25 + 0.15 * math.sin(self.t * 2.3) + random.gauss(0.0, 0.02)
            real_w = 1.1 + 0.6 * math.cos(self.t * 1.7) + random.gauss(0.0, 0.03)


        # 2. Интегрируем кинематику
        self.yaw += real_w * self.dt
        self.x += real_v * math.cos(self.yaw) * self.dt
        self.y += real_v * math.sin(self.yaw) * self.dt

        # Кватернион из yaw
        qz = math.sin(self.yaw / 2.0)
        qw = math.cos(self.yaw / 2.0)

        # 3. Публикуем /cmd_vel
        self.cmd_pub.publish(cmd)

        # 4. Публикуем /odom
        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = 'map'
        odom.child_frame_id = 'base_link'

        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw

        odom.twist.twist.linear.x = real_v
        odom.twist.twist.angular.z = real_w
        self.odom_pub.publish(odom)

        # 5. Публикуем TF: map -> base_link
        tf_msg = TransformStamped()
        tf_msg.header.stamp = now
        tf_msg.header.frame_id = 'map'
        tf_msg.child_frame_id = 'base_link'

        tf_msg.transform.translation.x = self.x
        tf_msg.transform.translation.y = self.y
        tf_msg.transform.translation.z = 0.0
        tf_msg.transform.rotation.z = qz
        tf_msg.transform.rotation.w = qw

        self.tf_broadcaster.sendTransform(tf_msg)


def main(args=None):
    rclpy.init(args=args)
    node = MockRobotNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
