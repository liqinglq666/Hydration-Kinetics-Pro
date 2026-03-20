from dataclasses import dataclass, field
import numpy as np
from typing import Optional, List, Tuple, Dict


@dataclass
class KineticsParameters:
    # ==========================================
    # 核心物理参量 (无默认值，严格遵循内存排布)
    # ==========================================
    t0_h: float
    qmax_j_g: float
    t50_h: float
    n: float
    k1: float
    k2: float
    k3: float
    alpha_1: float
    alpha_2: float

    # ==========================================
    # 衍生评估与特征跨度参量
    # ==========================================
    r2_ng: float = 0.0
    r2_i: float = 0.0
    r2_d: float = 0.0

    t_alpha_1_h: float = 0.0
    t_alpha_2_h: float = 0.0
    delta_alpha: float = 0.0
    delta_time_h: float = 0.0

    t_peak_h: float = 0.0
    t_end_h: float = 0.0
    induction_duration_h: float = 0.0
    accel_duration_h: float = 0.0
    decel_duration_h: float = 0.0

    peaks: List[Tuple[float, float]] = field(default_factory=list)

    # ==========================================
    # Origin 绘图专用数据包裹 (分类存储)
    # ==========================================
    origin_knudsen: Dict[str, np.ndarray] = field(default_factory=dict)
    origin_kd_linear: Dict[str, np.ndarray] = field(default_factory=dict)
    origin_rates: Dict[str, np.ndarray] = field(default_factory=dict)


@dataclass
class HydrationData:
    time_h: np.ndarray
    heat_flow_mw_g: np.ndarray
    cumulative_heat_j_g: np.ndarray
    alpha: Optional[np.ndarray] = None