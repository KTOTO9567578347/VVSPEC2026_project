#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <vector>
#include <functional>
#include <unordered_map>
#include <chrono>
#include <mutex>

#include "rclcpp/rclcpp.hpp"
#include "nlohmann/json.hpp"

#include "std_msgs/msg/string.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "nav_msgs/msg/odometry.hpp"

#include "tf2_ros/buffer.h"
#include "tf2_ros/transform_listener.h"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"

#include "telemetry.pb.h"
#include "telemetry.grpc.pb.h"

#include <grpcpp/grpcpp.h>

class grpc_subscriber: public rclcpp::Node{
    public:
        grpc_subscriber(const std::string& json_path): Node("grpc_subscriber"), tf_buffer_(this->get_clock()), tf_listener_(tf_buffer_){
            parse_json_config(json_path);

            fast_record_timer_ = this->create_wall_timer(
                std::chrono::milliseconds(50),
                std::bind(&grpc_subscriber::fast_record_timer_callback, this)
            );

            slow_send_timer_ = this->create_wall_timer(
                std::chrono::seconds(5),
                std::bind(&grpc_subscriber::slow_send_timer_callback, this)
            );
            
        }

        template <typename MessageT>
        void process_message(const std::string& topic, const typename MessageT::SharedPtr msg){
            RCLCPP_INFO(this->get_logger(), "[%s]: Получено сообщение типа %s", topic.c_str(), typeid(MessageT).name());
        }

    private:
        std::string grpc_server_address_ = "localhost:50051";

        bool tf_enabled_ = true;
        bool fallback_to_odom_ = true;
        std::string global_frame_ = "map";
        std::string robot_frame_ = "base_link";

        std::vector<std::shared_ptr<rclcpp::SubscriptionBase>> subscribers_;
        using SubscriberCreator = std::function<void(const std::string&, const rclcpp::QoS&)>;

        tf2_ros::Buffer tf_buffer_;
        tf2_ros::TransformListener tf_listener_;

        rclcpp::TimerBase::SharedPtr fast_record_timer_;
        rclcpp::TimerBase::SharedPtr slow_send_timer_;

        std::mutex state_mutex_;
        double last_cmd_linear_x_ = 0.0;
        double last_cmd_angular_z_ = 0.0;
        double last_odom_linear_x_ = 0.0;
        double last_odom_angular_z_ = 0.0;

        std::mutex batch_mutex_;
        std::vector<robot_telemetry::TelemetryPoint> batch_buffer_;

        std::shared_ptr<grpc::Channel> channel_;
        std::unique_ptr<robot_telemetry::TelemetryService::Stub> grpc_stub_;

        void fast_record_timer_callback() {
            if (!tf_enabled_) return;

            robot_telemetry::TelemetryPoint point;

            auto now = std::chrono::system_clock::now();
            point.set_timestamp_ms(std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count());

            try {
                geometry_msgs::msg::TransformStamped tf_msg = 
                    tf_buffer_.lookupTransform(global_frame_, robot_frame_, tf2::TimePointZero);

                point.set_status(robot_telemetry::TelemetryStatus::OK);

                auto* pose = point.mutable_pose();
                pose->set_x(tf_msg.transform.translation.x);
                pose->set_y(tf_msg.transform.translation.y);

                tf2::Quaternion q(tf_msg.transform.rotation.x, tf_msg.transform.rotation.y, tf_msg.transform.rotation.z, tf_msg.transform.rotation.w);
                double roll, pitch, yaw;
                tf2::Matrix3x3(q).getRPY(roll, pitch, yaw);
                pose->set_yaw(yaw);

            } catch (const tf2::TransformException& ex) {
                point.set_status(robot_telemetry::TelemetryStatus::NOTF);
                point.set_status_message(ex.what());
            }

            {
                std::lock_guard<std::mutex> lock(state_mutex_);

                auto* cmd = point.mutable_cmd_vel();
                cmd->set_linear_x(last_cmd_linear_x_);
                cmd->set_angular_z(last_cmd_angular_z_);

                auto* odom = point.mutable_odom_vel();
                odom->set_linear_x(last_odom_linear_x_);
                odom->set_angular_z(last_odom_angular_z_);
            }

            {
                std::lock_guard<std::mutex> lock(batch_mutex_);
                batch_buffer_.push_back(point);
            }
        }

        void slow_send_timer_callback() {
            robot_telemetry::TelemetryBatchRequest batch_request;
            batch_request.set_robot_id("robot_v1_simulation");

            {
                std::lock_guard<std::mutex> lock(batch_mutex_);
                if (batch_buffer_.empty()) {
                    return; 
                }
            
                for (auto& point : batch_buffer_) {
                    auto* allocated_point = batch_request.add_points();
                    *allocated_point = std::move(point);
                }
                batch_buffer_.clear();
            }

            grpc::ClientContext context;
            robot_telemetry::TelemetryResponse response;
        
            // --- ФИНАЛЬНАЯ ОТПРАВКА БАТЧА В СЕТЬ ПО gRPC ---
            RCLCPP_INFO(this->get_logger(), "[gRPC Батчинг] Отправляем пакет из %d точек истории за последние 5 секунд.", batch_request.points_size());

            grpc::Status status = grpc_stub_->SendTelemetryBatch(&context, batch_request, &response);

            if (!status.ok()) {
            RCLCPP_ERROR(this->get_logger(), "[gRPC Мост] Ошибка отправки: %s (Код: %d)", 
                status.error_message().c_str(), status.error_code());
            } else {
                RCLCPP_INFO(this->get_logger(), "[gRPC Мост] Батч успешно доставлен на сервер!");
            }
        }


        template <typename MessageT>
        void register_templated_sub(const std::string& topic, const rclcpp::QoS& qos){
            auto sub = this->create_subscription<MessageT>(
                topic, qos,
                [this, topic](const typename MessageT::SharedPtr msg) {
                    this->process_message<MessageT>(topic, msg);
                }
            );

            subscribers_.push_back(sub);
        }

        const std::unordered_map<std::string, SubscriberCreator> type_registry_ = {
            { "std_msgs/msg/String", [this](auto&&... args) { this->register_templated_sub<std_msgs::msg::String>(args...); } },
            { "geometry_msgs/msg/Twist", [this](auto&&... args) { this->register_templated_sub<geometry_msgs::msg::Twist>(args...); } },
            { "nav_msgs/msg/Odometry", [this](auto&&... args) { this->register_templated_sub<nav_msgs::msg::Odometry>(args...); } },
        };

        void create_subscriber(const std::string& topic_name, const std::string& topic_dtype, const std::string& topic_qos){
            rclcpp::QoS qos = (topic_qos == "sensor_data") ? rclcpp::SensorDataQoS() : rclcpp::QoS(10);

            auto type_it = type_registry_.find(topic_dtype);
            if (type_it != type_registry_.end()){
                type_it->second(topic_name, qos);
            } else {
                RCLCPP_ERROR(this->get_logger(), "Тип '%s' не зарегистрирован!", topic_dtype.c_str());
            }
        }

        void parse_json_config(const std::string& json_path){
            nlohmann::json config;
            std::fstream file(json_path);
            file >> config;

            for (auto topic_descr: config["subscribers"]){
                create_subscriber(topic_descr["topic"], topic_descr["type"], topic_descr["qos"]);
            }

            if (config.contains("tf_settings")){
                auto tf_cfg = config["tf_settings"];
                tf_enabled_ = tf_cfg.value("enabled", true);
                fallback_to_odom_ = tf_cfg.value("fallback_to_odom", true);
                global_frame_ = tf_cfg.value("global_frame", "map");
                robot_frame_ = tf_cfg.value("robot_frame", "base_link");
            }

            if (config.contains("grpc_settings")) {
                grpc_server_address_ = config["grpc_settings"].value("server_address", "localhost:50051");
                channel_ = grpc::CreateChannel(grpc_server_address_, grpc::InsecureChannelCredentials());
                grpc_stub_ = robot_telemetry::TelemetryService::NewStub(channel_);
            }
        }
};

template<>
void grpc_subscriber::process_message<std_msgs::msg::String>(const std::string& topic, const std_msgs::msg::String::SharedPtr msg) {
    RCLCPP_INFO(this->get_logger(), "[%s]: Текстовое сообщение: '%s'", topic.c_str(), msg->data.c_str());
}

template<>
void grpc_subscriber::process_message<geometry_msgs::msg::Twist>(const std::string& /*topic*/, const geometry_msgs::msg::Twist::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    last_cmd_linear_x_ = msg->linear.x;
    last_cmd_angular_z_ = msg->angular.z;
}

template<>
void grpc_subscriber::process_message<nav_msgs::msg::Odometry>(const std::string& /*topic*/, const nav_msgs::msg::Odometry::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    last_odom_linear_x_ = msg->twist.twist.linear.x;
    last_odom_angular_z_ = msg->twist.twist.angular.z;
}

int main(int argc, char * argv[]){
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<grpc_subscriber>("config.json"));
    rclcpp::shutdown();
    return 0;
}