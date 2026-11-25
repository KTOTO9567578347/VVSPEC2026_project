from collections import defaultdict, deque
from pathlib import Path
from pickle import load
import numpy as np
from sklearn.linear_model import LinearRegression

from app.schemas.payload import AnomalyPrediction


def compute_tracking_metrics(
    data_dict: dict,
    model_v: LinearRegression | None = None,
    model_w: LinearRegression | None = None,
) -> dict[str, float]:
    """
    Вычисляет RMSE слежения по линейной (v) и угловой (w) скоростям.
    """
    odometries = data_dict.get('odometries', [])
    cmd_vels = data_dict.get('cmd_vels', [])

    n = min(len(odometries), len(cmd_vels))
    if n < 2:
        return {'rmse_linear': 0.0, 'rmse_angular': 0.0}

    odom_slice = odometries[-n:]
    cmd_slice = cmd_vels[-n:]

    actual_v = np.array([float(o['linear_velocity']['x']) for o in odom_slice])
    actual_w = np.array([float(o['angular_velocity']['z']) for o in odom_slice])

    cmd_v = np.array([float(c['linear']['x']) for c in cmd_slice])
    cmd_w = np.array([float(c['angular']['z']) for c in cmd_slice])

    if model_v is not None and model_w is not None:
        X_v = np.column_stack((cmd_v[1:], actual_v[:-1]))
        X_w = np.column_stack((cmd_w[1:], actual_w[:-1]))

        expected_v = model_v.predict(X_v)
        expected_w = model_w.predict(X_w)

        target_v = actual_v[1:]
        target_w = actual_w[1:]
    else:
        expected_v = cmd_v
        expected_w = cmd_w
        target_v = actual_v
        target_w = actual_w

    rmse_v = float(np.sqrt(np.mean((target_v - expected_v) ** 2)))
    rmse_w = float(np.sqrt(np.mean((target_w - expected_w) ** 2)))

    return {
        'rmse_linear': round(rmse_v, 4),
        'rmse_angular': round(rmse_w, 4),
    }


def is_robot_idle(odometries: list[dict], threshold: float = 0.01) -> bool:
    for item in odometries:
        lin = abs(float(item['linear_velocity']['x']))
        ang = abs(float(item['angular_velocity']['z']))
        if lin + ang > threshold:
            return False
    return True


class AnomalyDetector:
    """
    Мультироботный детектор аномалий:
    - Поддерживает индивидуальные веса Модели 1 для каждого robot_id (с фолбэком на общую модель).
    - Ведет изолированную историю трендов RMSE (Модель 2) для каждого robot_id.
    """

    def __init__(
        self,
        models_dir: Path | None = None,
        rmse_v_threshold: float = 0.15,
        rmse_w_threshold: float = 0.25,
        trend_slope_threshold: float = 0.02,
        history_size: int = 10,
    ):
        self.models_dir = models_dir or Path(__file__).parent
        self.rmse_v_threshold = rmse_v_threshold
        self.rmse_w_threshold = rmse_w_threshold
        self.trend_slope_threshold = trend_slope_threshold
        self.history_size = history_size

        # Кэш загруженных моделей по robot_id: {robot_id: (model_v, model_w)}
        self._robot_models: dict[str, tuple[LinearRegression | None, LinearRegression | None]] = {}

        # Изолированные истории RMSE для Модели 2 по robot_id
        self._rmse_histories: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.history_size)
        )

    def _get_models_for_robot(
        self, robot_id: str
    ) -> tuple[LinearRegression | None, LinearRegression | None]:
        """Возвращает (model_v, model_w) для конкретного робота или общую модель."""
        if robot_id in self._robot_models:
            return self._robot_models[robot_id]

        specific_path = self.models_dir / f'kinematic_models_{robot_id}.pkl'
        default_path = self.models_dir / 'kinematic_models.pkl'

        target_path = specific_path if specific_path.exists() else default_path

        if target_path.exists():
            with open(target_path, 'rb') as f:
                models = load(f)
                pair = (models.get('model_v'), models.get('model_w'))
        else:
            pair = (None, None)

        self._robot_models[robot_id] = pair
        return pair

    def _compute_rmse_trend_slope(self, robot_id: str) -> float:
        """Модель 2: линейная регрессия тренда RMSE для конкретного робота."""
        history = self._rmse_histories[robot_id]
        if len(history) < 4:
            return 0.0

        y = np.array(history)
        x = np.arange(len(y)).reshape(-1, 1)

        trend_model = LinearRegression().fit(x, y)
        return float(trend_model.coef_[0])

    def analyze(
        self, data_dict: dict, check_idle: bool = False
    ) -> tuple[dict[str, float], AnomalyPrediction | None]:
        robot_id = str(data_dict.get('robot_id', 'default'))
        odometries = data_dict.get('odometries', [])

        if len(odometries) < 2:
            return {'rmse_linear': 0.0, 'rmse_angular': 0.0, 'rmse_trend_slope': 0.0}, None

        # 1. Получаем индивидуальные (или общие) веса Модели 1 и считаем RMSE
        model_v, model_w = self._get_models_for_robot(robot_id)
        metrics = compute_tracking_metrics(data_dict, model_v, model_w)
        rmse_v = metrics['rmse_linear']
        rmse_w = metrics['rmse_angular']

        # 2. Обновляем тренд Модели 2 для этого робота
        self._rmse_histories[robot_id].append(rmse_v + rmse_w)
        slope = self._compute_rmse_trend_slope(robot_id)
        metrics['rmse_trend_slope'] = round(slope, 4)

        # 3. Проверка на полный простой
        if check_idle and is_robot_idle(odometries):
            return metrics, AnomalyPrediction(
                anomaly_type='route_not_found',
                confidence=1.0,
                message='Вердикт системы аналитики: робот стоит на месте.',
            )

        # 4. Проверка порогов RMSE
        if rmse_v > self.rmse_v_threshold or rmse_w > self.rmse_w_threshold:
            ratio = max(rmse_v / self.rmse_v_threshold, rmse_w / self.rmse_w_threshold)
            conf = min(1.0, 0.5 + 0.25 * ratio)
            return metrics, AnomalyPrediction(
                anomaly_type='tracking_anomaly',
                confidence=round(conf, 2),
                message=(
                    f'Вердикт системы аналитики: нарушение слежения за командой '
                    f'(RMSE_v={rmse_v:.3f}, RMSE_w={rmse_w:.3f}).'
                ),
            )

        # 5. Проверка устойчивого роста ошибки (тренд Модели 2)
        if slope > self.trend_slope_threshold:
            return metrics, AnomalyPrediction(
                anomaly_type='degradation_trend',
                confidence=0.75,
                message=f'Вердикт системы аналитики: устойчивый рост ошибки слежения (тренд k={slope:.3f}).',
            )

        return metrics, None

    def predict_with_confidence(
        self, data_dict: dict, check_idle: bool = False
    ) -> AnomalyPrediction | None:
        _, prediction = self.analyze(data_dict, check_idle=check_idle)
        return prediction

    def predict(self, data_dict: dict, check_idle: bool = False) -> str:
        _, prediction = self.analyze(data_dict, check_idle=check_idle)
        return prediction.message if prediction else ''
