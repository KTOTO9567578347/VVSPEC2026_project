import math
from pathlib import Path
from pickle import load
import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import savgol_filter

from app.schemas.payload import AnomalyPrediction

FEATURE_KEYS = [
    'cleaned_avg_linear_speed', 'speed_variance', 'angular_zcr',
    'mid_stop_ratio', 'zcr_angular_vel', 'progress_consistency',
    'angular_smoothness', 'area_redundancy', 'oscillation_ratio',
    'acceleration_stability', 'velocity_direction_coherence',
    'trajectory_entropy', 'hurst_exponent', 'jarque_bera_acceleration',
    'path_curvature', 'speed_coefficient_of_variation'
]


def _flatten_odometry(inp: dict) -> dict:
    return {
        'frame_id': inp['frame_id'],
        'timestamp': inp['timestamp'],
        'position_x': inp['position']['x'],
        'position_y': inp['position']['y'],
        'position_z': inp['position']['z'],
        'orientation_x': inp['orientation']['x'],
        'orientation_y': inp['orientation']['y'],
        'orientation_z': inp['orientation']['z'],
        'orientation_w': inp['orientation']['w'],
        'linear_velocity_x': inp['linear_velocity']['x'],
        'linear_velocity_y': inp['linear_velocity']['y'],
        'linear_velocity_z': inp['linear_velocity']['z'],
        'angular_velocity_x': inp['angular_velocity']['x'],
        'angular_velocity_y': inp['angular_velocity']['y'],
        'angular_velocity_z': inp['angular_velocity']['z'],
    }


def compute_behavioral_indicators(data_dict: dict) -> dict[str, float]:
    """Вычисляет 16 поведенческих индикаторов по массиву одометрии."""
    raw_odometries = data_dict.get('odometries', [])
    n_samples = len(raw_odometries)

    if n_samples == 0:
        return {k: 0.0 for k in FEATURE_KEYS}

    odometries = [_flatten_odometry(item) for item in raw_odometries]
    pos_x = np.array([float(o.get('position_x', 0.0)) for o in odometries])
    pos_y = np.array([float(o.get('position_y', 0.0)) for o in odometries])

    # Интервал дискретизации
    try:
        ts = np.array([float(o['timestamp']) for o in odometries])
        if ts.max() > 1e9:  # ms -> s
            ts /= 1000.0
        valid_diffs = np.diff(ts)
        valid_diffs = valid_diffs[valid_diffs > 0]
        sampling_interval = float(np.median(valid_diffs)) if len(valid_diffs) > 0 else 0.5
    except Exception:
        sampling_interval = 0.5

    # Сглаживание траектории
    win = min(9, max(5, n_samples // 10))
    if n_samples >= win:
        try:
            pos_x_s = savgol_filter(pos_x, win, 2)
            pos_y_s = savgol_filter(pos_y, win, 2)
        except Exception:
            k = np.ones(win) / win
            pos_x_s = np.convolve(pos_x, k, 'same')
            pos_y_s = np.convolve(pos_y, k, 'same')
            h = win // 2
            if h > 0:
                pos_x_s[:h], pos_x_s[-h:] = pos_x[:h], pos_x[-h:]
                pos_y_s[:h], pos_y_s[-h:] = pos_y[:h], pos_y[-h:]
    else:
        pos_x_s, pos_y_s = pos_x, pos_y

    # Кинематика
    vel_x = np.gradient(pos_x_s, sampling_interval)
    vel_y = np.gradient(pos_y_s, sampling_interval)
    speed_raw = np.hypot(vel_x, vel_y)

    if n_samples >= 5:
        speed_diff = np.abs(np.diff(speed_raw))
        noise_level = np.percentile(speed_diff, 25) if speed_diff.size > 0 else 0.01
        speed_c = speed_raw.copy()
        r = min(2, n_samples // 20)
        for i in range(r, n_samples - r):
            w = speed_raw[i - r:i + r + 1]
            if np.std(w) > noise_level * 2:
                speed_c[i] = np.median(w)
    else:
        speed_c = speed_raw

    avg_speed = float(np.mean(speed_c))
    max_speed = float(np.max(speed_c))

    if n_samples > 1:
        dx = np.diff(pos_x_s)
        dy = np.diff(pos_y_s)
        unwrapped_angles = np.unwrap(np.arctan2(dy, dx))
        segment_lengths = np.hypot(dx, dy) + 1e-8
        fdir_x = dx / segment_lengths
        fdir_y = dy / segment_lengths

        forward_speed = np.zeros(n_samples)
        forward_speed[0] = vel_x[0] * fdir_x[0] + vel_y[0] * fdir_y[0]
        forward_speed[-1] = vel_x[-1] * fdir_x[-1] + vel_y[-1] * fdir_y[-1]
        if n_samples > 2:
            forward_speed[1:-1] = vel_x[1:-1] * fdir_x[:-1] + vel_y[1:-1] * fdir_y[:-1]
    else:
        unwrapped_angles = np.array([])
        forward_speed = np.zeros(n_samples)

    indicators = {}

    # 1. cleaned_avg_linear_speed
    indicators['cleaned_avg_linear_speed'] = np.clip(avg_speed / max(0.1, max_speed), 0.0, 1.0)

    # 2. speed_variance
    if n_samples > 1:
        variance_norm = np.std(speed_c) / (avg_speed * 0.8 + 0.1 + 1e-8)
        indicators['speed_variance'] = 1.0 - np.clip(variance_norm, 0.0, 1.0)
    else:
        indicators['speed_variance'] = 1.0

    # 3. angular_zcr
    if n_samples > 3 and len(unwrapped_angles) >= 2:
        ang_vel = np.diff(unwrapped_angles) / sampling_interval
        zc_count = sum(
            1 for i in range(1, len(ang_vel))
            if ang_vel[i - 1] != 0 and ang_vel[i] != 0 and ang_vel[i - 1] * ang_vel[i] < 0
        )
        zc_rate = zc_count / (len(ang_vel) + 1e-8)
        indicators['angular_zcr'] = 1.0 - np.clip(zc_rate / 0.3, 0.0, 1.0)
    else:
        indicators['angular_zcr'] = 1.0

    # 4. mid_stop_ratio
    if n_samples > 1:
        stopped = speed_c < 0.1
        non_stopped_idx = np.flatnonzero(~stopped)
        if len(non_stopped_idx) > 1:
            s_idx, e_idx = non_stopped_idx[0], non_stopped_idx[-1]
            mid_stop_ratio = np.sum(stopped[s_idx:e_idx + 1]) / n_samples
        else:
            mid_stop_ratio = 0.0
        indicators['mid_stop_ratio'] = 1.0 - np.clip(mid_stop_ratio, 0.0, 1.0)
    else:
        indicators['mid_stop_ratio'] = 1.0

    # 5. zcr_angular_vel
    if n_samples > 2:
        zc_count = sum(
            1 for i in range(1, n_samples)
            if forward_speed[i - 1] != 0 and forward_speed[i] != 0 and forward_speed[i - 1] * forward_speed[i] < 0
        )
        zc_rate = zc_count / max(1e-8, (n_samples - 1) * sampling_interval)
        indicators['zcr_angular_vel'] = 1.0 - np.clip(zc_rate / 2.0, 0.0, 1.0)
    else:
        indicators['zcr_angular_vel'] = 1.0

    # 6. progress_consistency
    if n_samples >= 2:
        path_len = float(np.sum(np.hypot(np.diff(pos_x), np.diff(pos_y))))
        final_len = math.dist((pos_x[0], pos_y[0]), (pos_x[-1], pos_y[-1]))
        consistency = final_len / (path_len + 1e-8) if path_len > 0.02 else 0.0
        indicators['progress_consistency'] = np.clip(consistency, 0.0, 1.0)
    else:
        indicators['progress_consistency'] = 0.0

    # 7. angular_smoothness
    if n_samples > 4 and len(unwrapped_angles) >= 3:
        ang_vel = np.diff(unwrapped_angles) / sampling_interval
        delta_ang_vel = np.abs(np.diff(ang_vel))
        if len(delta_ang_vel) > 0:
            threshold = np.percentile(delta_ang_vel, 75) + 0.5 * np.std(delta_ang_vel)
            indicators['angular_smoothness'] = 1.0 - float(np.mean(delta_ang_vel > threshold))
        else:
            indicators['angular_smoothness'] = 1.0
    else:
        indicators['angular_smoothness'] = 1.0

    # 8. area_redundancy
    if n_samples >= 3:
        mean_x, mean_y = np.mean(pos_x_s), np.mean(pos_y_s)
        avg_dist = float(np.mean(np.hypot(pos_x_s - mean_x, pos_y_s - mean_y)))
        total_dist = float(np.sum(np.hypot(np.diff(pos_x_s), np.diff(pos_y_s))))
        ratio = avg_dist / (total_dist + 1e-8)
        indicators['area_redundancy'] = np.clip(ratio / 0.25, 0.0, 1.0)
    else:
        indicators['area_redundancy'] = 1.0

    # 9. oscillation_ratio
    if n_samples >= 15:
        end_idx = max(10, int(0.8 * n_samples))
        final_pos = (pos_x_s[-1], pos_y_s[-1])
        oscillations = 0
        for i in range(end_idx, n_samples - 1):
            curr_d = math.dist((pos_x_s[i], pos_y_s[i]), final_pos)
            next_d = math.dist((pos_x_s[i + 1], pos_y_s[i + 1]), final_pos)
            if curr_d < 0.3 and next_d > curr_d * 1.2:
                oscillations += 1
        osc_ratio = oscillations / (n_samples - end_idx + 1e-8)
        indicators['oscillation_ratio'] = 1.0 - np.clip(osc_ratio * 3, 0.0, 1.0)
    else:
        indicators['oscillation_ratio'] = 1.0

    # 10. acceleration_stability
    if n_samples > 3:
        max_accel = float(np.max(np.abs(np.gradient(speed_c, sampling_interval))))
        indicators['acceleration_stability'] = 1.0 - np.clip(max_accel / 0.8, 0.0, 1.0)
    else:
        indicators['acceleration_stability'] = 1.0

    # 11. velocity_direction_coherence
    if n_samples > 2:
        coherence_count, total_count = 0, 0
        for i in range(n_samples - 1):
            if speed_c[i] < 0.05:
                continue
            total_count += 1
            mdx, mdy = pos_x_s[i + 1] - pos_x_s[i], pos_y_s[i + 1] - pos_y_s[i]
            mnorm = math.hypot(mdx, mdy) + 1e-8
            vnorm = speed_c[i] + 1e-8
            cos_angle = (mdx / mnorm) * (vel_x[i] / vnorm) + (mdy / mnorm) * (vel_y[i] / vnorm)
            if math.acos(max(-1.0, min(1.0, cos_angle))) < math.pi / 4:
                coherence_count += 1
        indicators['velocity_direction_coherence'] = (coherence_count / total_count) if total_count > 0 else 1.0
    else:
        indicators['velocity_direction_coherence'] = 1.0

    # 12. trajectory_entropy
    if n_samples >= 5:
        x_min, x_max = np.min(pos_x_s), np.max(pos_x_s)
        y_min, y_max = np.min(pos_y_s), np.max(pos_y_s)
        cell_x = ((pos_x_s - x_min) / (max(x_max - x_min, 0.1) / 10)).astype(int)
        cell_y = ((pos_y_s - y_min) / (max(y_max - y_min, 0.1) / 10)).astype(int)
        _, counts = np.unique(np.column_stack((cell_x, cell_y)), axis=0, return_counts=True)
        probs = counts / n_samples
        entropy = -float(np.sum(probs * np.log2(probs)))
        max_entropy = math.log2(min(100, n_samples))
        indicators['trajectory_entropy'] = 1.0 - np.clip(entropy / max_entropy if max_entropy > 0 else 0.0, 0.0, 1.0)
    else:
        indicators['trajectory_entropy'] = 1.0

    # 13. hurst_exponent
    if n_samples >= 10 and avg_speed > 0.01:
        cum_dev = np.cumsum(speed_c - avg_speed)
        r_s_values = []
        for window in (5, 10, 20, 30):
            if window >= n_samples:
                continue
            ratios = []
            for i in range(0, n_samples - window + 1, window):
                seg = cum_dev[i:i + window]
                r = np.max(seg) - np.min(seg)
                s = np.std(speed_c[i:i + window]) + 1e-8
                ratios.append(r / s)
            if ratios:
                r_s_values.append((window, np.mean(ratios)))
        if len(r_s_values) >= 2:
            slope, _ = np.polyfit(np.log([x[0] for x in r_s_values]), np.log([x[1] for x in r_s_values]), 1)
            indicators['hurst_exponent'] = np.clip(1.0 - abs(slope - 0.5) * 2, 0.0, 1.0)
        else:
            indicators['hurst_exponent'] = 0.5
    else:
        indicators['hurst_exponent'] = 0.5

    # 14. jarque_bera_acceleration
    if n_samples >= 5:
        acceleration = np.gradient(speed_c, sampling_interval)
        if len(acceleration) >= 4:
            try:
                jb_stat, _ = stats.jarque_bera(acceleration)
                indicators['jarque_bera_acceleration'] = 1.0 - min(jb_stat / 5.991, 1.0)
            except Exception:
                indicators['jarque_bera_acceleration'] = 1.0
        else:
            indicators['jarque_bera_acceleration'] = 1.0
    else:
        indicators['jarque_bera_acceleration'] = 1.0

    # 15. path_curvature
    if n_samples >= 5:
        dx1 = np.diff(pos_x_s[:-1]) / sampling_interval
        dy1 = np.diff(pos_y_s[:-1]) / sampling_interval
        dx2 = np.diff(pos_x_s, n=2) / (sampling_interval ** 2)
        dy2 = np.diff(pos_y_s, n=2) / (sampling_interval ** 2)
        curvatures = np.abs(dx1 * dy2 - dy1 * dx2) / ((dx1 ** 2 + dy1 ** 2 + 1e-8) ** 1.5)
        indicators['path_curvature'] = 1.0 - min(float(np.mean(curvatures)) / 0.1, 1.0)
    else:
        indicators['path_curvature'] = 1.0

    # 16. speed_coefficient_of_variation
    if n_samples > 1 and avg_speed > 0.01:
        cv = np.std(speed_c) / avg_speed
        indicators['speed_coefficient_of_variation'] = 1.0 - min(float(cv), 1.0)
    else:
        indicators['speed_coefficient_of_variation'] = 1.0

    return {k: float(np.clip(indicators[k], 0.0, 1.0)) for k in FEATURE_KEYS}


def is_robot_idle(odometry: list[dict], threshold: float = 0.01) -> bool:
    for item in odometry:
        lin = sum(abs(item['linear_velocity'][axis]) for axis in ('x', 'y', 'z'))
        ang = sum(abs(item['angular_velocity'][axis]) for axis in ('x', 'y', 'z'))
        if lin + ang > threshold:
            return False
    return True


class AnomalyDetector:
    def __init__(self, model_path: Path | None = None, threshold: float = 0.6):
        path = model_path or (Path(__file__).parent / 'classifier.pkl')
        with open(path, 'rb') as f:
            self.classifier = load(f)
        self.threshold = threshold

    def predict_with_confidence(
        self, data_dict: dict, check_idle: bool = False
    ) -> AnomalyPrediction | None:
        odometry = data_dict.get('odometries', [])
        if len(odometry) < 2:
            return None

        if check_idle and is_robot_idle(odometry):
            return AnomalyPrediction(
                anomaly_type='route_not_found',
                confidence=1.0,
                message='Вердикт системы аналитики аномалий: Маршрут не найден, робот стоит на месте.',
            )

        indicators = compute_behavioral_indicators(data_dict)
        features_df = pd.DataFrame([indicators], columns=FEATURE_KEYS)
        anomaly_prob = self.classifier.predict_proba(features_df)[0, 1]

        if anomaly_prob < self.threshold:
            return None

        return AnomalyPrediction(
            anomaly_type='abnormal_movement',
            confidence=float(anomaly_prob),
            message='Вердикт системы аналитики аномалий: Аномальное движение, робот сбит с толку.',
        )

    def predict(self, data_dict: dict, check_idle: bool = False) -> str:
        prediction = self.predict_with_confidence(data_dict, check_idle=check_idle)
        return prediction.message if prediction else ''
