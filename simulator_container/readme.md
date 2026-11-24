# ROS 2 Jazzy workspace

Проект использует [Flatland](https://github.com/OpenRobOps/sim-flatland) вместо `nav2_loopback_sim`. Flatland публикует `/odom`, `/scan` и TF; Nav2 использует AMCL для локализации по статической карте или SLAM, если включён режим SLAM.

## Быстрый запуск

1. Соберите и запустите контейнер:

```bash
docker compose up -d --build
```

2. Войдите в контейнер:

```bash
docker compose exec ros bash
```

3. Соберите workspace и запустите демонстрацию:

```bash
make build-all
source /opt/ros/jazzy/setup.bash
source /src/install/setup.bash
ros2 launch main demo.yaml
```

При запуске сервисов Flatland загружает карту `packages/main/maps/maze.yaml`, модель робота `packages/main/worlds/robot.model.yaml` и модель мира `packages/main/worlds/maze.world.yaml`.

## Запуск режимов

Статическая карта с AMCL (поддерживается `false`/`False` и `true`/`True`):

```bash
ros2 launch main demo.yaml use_slam:=false
```

SLAM вместо статической карты и AMCL:

```bash
ros2 launch main demo.yaml use_slam:=true
```

Проверить основные топики Flatland:

```bash
ros2 topic echo /odom --once
ros2 topic echo /scan --once
ros2 topic hz /scan
ros2 topic echo /tf --once
```

## Телеметрия (`grpc_bridge`)

В отдельном терминале внутри контейнера из корня workspace (`/src`, где лежит `config.json`) для отправки телеметрии в `backend_ml` (`localhost:50051`):

```bash
ros2 run grpc_bridge grpc_bridge_node
```

## Foxglove

`ros2 launch main demo.yaml` уже поднимает `foxglove_bridge` на `ws://localhost:8765`.
Отдельный запуск нужен только если вы стартуете `bringup_launch.py` напрямую (параллельный запуск вместе с `demo.yaml` упадёт из-за занятого порта `8765`):

```bash
ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765 address:=0.0.0.0 use_sim_time:=true
```

## Пересборка и остановка

Пересобрать workspace без Flatland image:

```bash
make build-all
```

Пересобрать образ после изменений в `dockerfile`:

```bash
docker compose build ros
```

Остановить проект:

```bash
docker compose down
```
