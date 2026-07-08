import re
from pathlib import Path
from typing import Literal

import pandas as pd

from core.data_models import HydrationData
from utils.exceptions import DataParserError
from utils.logger import logger


InputMode = Literal["total", "normalized"]


class CalorimetryParser:
    """Parse calorimetry data with explicit unit normalization.

    input_mode="total": columns are total heat flow (mW) and total cumulative heat (J),
    so values are divided by sample_mass_g.

    input_mode="normalized": columns are already mass-normalized heat flow (mW/g)
    and cumulative heat (J/g), so sample_mass_g is validated but not applied.
    """

    def __init__(self, sample_mass_g: float = 1.0, input_mode: InputMode = "total") -> None:
        self.sample_mass_g = float(sample_mass_g)
        self.input_mode = input_mode

    def parse(self, file_path: Path) -> HydrationData:
        if not file_path.exists():
            raise DataParserError(f"目标文件不存在: {file_path.absolute()}")

        if self.sample_mass_g <= 0:
            raise DataParserError("样品质量必须大于 0 g。")

        if self.input_mode not in {"total", "normalized"}:
            raise DataParserError("输入单位模式非法。请选择 total 或 normalized。")

        try:
            suffix = file_path.suffix.lower()
            if suffix == ".csv":
                df = self._read_csv(file_path)
            elif suffix == ".xlsx":
                df = pd.read_excel(file_path)
            else:
                raise DataParserError("不支持的文件格式。当前仅支持 .csv 和 .xlsx；旧式 .xls 请先另存为 .xlsx。")

            df = self._normalize_columns(df)

            target_cols = ["time_h", "heat_flow", "cumulative_heat"]
            missing_cols = [col for col in target_cols if col not in df.columns]
            if missing_cols:
                raise DataParserError(
                    "数据表缺少关键列: "
                    f"{', '.join(missing_cols)}。请确认表头包含时间、热流和累计热量。"
                )

            for col in target_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df.dropna(subset=target_cols, inplace=True)
            df.sort_values("time_h", inplace=True)
            df = df.drop_duplicates(subset="time_h", keep="first")

            if df.empty:
                raise DataParserError("数据清洗后为空，请检查文件内容是否为有效数值。")

            if len(df) < 2 or not df["time_h"].is_monotonic_increasing:
                raise DataParserError("时间列必须包含至少两个递增的数据点。")

            if df["time_h"].iloc[0] < 0:
                logger.warning("检测到负时间点，将保留原始时间序列用于完整追踪；请确认仪器基线设置。")

            if self.input_mode == "total":
                heat_flow_mw_g = df["heat_flow"] / self.sample_mass_g
                cumulative_heat_j_g = df["cumulative_heat"] / self.sample_mass_g
                logger.info("输入单位模式: total，总热流/总热量已按样品质量归一化。")
            else:
                heat_flow_mw_g = df["heat_flow"]
                cumulative_heat_j_g = df["cumulative_heat"]
                logger.info("输入单位模式: normalized，数据已视为 mW/g 与 J/g，不再除以质量。")

            logger.info(f"数据加载成功: {file_path.name} (解析引擎: {suffix})")

            return HydrationData(
                time_h=df["time_h"].to_numpy(dtype=float),
                heat_flow_mw_g=heat_flow_mw_g.to_numpy(dtype=float),
                cumulative_heat_j_g=cumulative_heat_j_g.to_numpy(dtype=float),
            )
        except DataParserError:
            raise
        except ImportError as e:
            logger.error(f"底层依赖缺失: {e}")
            raise DataParserError("无法读取 Excel 文件，请确认已安装 openpyxl。")
        except Exception as e:
            logger.error(f"解析器严重异常: {e}")
            raise DataParserError(f"数据解析遭遇未知失败: {str(e)}")

    def _read_csv(self, file_path: Path) -> pd.DataFrame:
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return pd.read_csv(file_path, encoding=encoding)
            except UnicodeDecodeError:
                logger.warning(f"{encoding} 解码失败，尝试下一种编码: {file_path.name}")
        raise DataParserError(f"无法识别 CSV 文件编码: {file_path.name}")

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        aliases = {
            "time_h": {
                "time_h",
                "time",
                "timeh",
                "timehour",
                "timehours",
                "elapsedtime",
                "elapsedtimeh",
                "时间",
                "时间h",
                "时间小时",
            },
            "heat_flow": {
                "heat_flow",
                "heat_flow_mw",
                "heat_flow_mw_g",
                "heatflow",
                "heatflowmw",
                "heatflowmwg",
                "power",
                "powermw",
                "热流",
                "热流mw",
                "热流mwg",
                "放热速率",
                "放热速率mw",
                "放热速率mwg",
            },
            "cumulative_heat": {
                "cumulative",
                "cumulative_heat",
                "cumulative_heat_j",
                "cumulative_heat_j_g",
                "cumulativeheat",
                "cumulativeheatj",
                "cumulativeheatjg",
                "totalheat",
                "totalheatj",
                "累计热量",
                "累积热量",
                "累计热量jg",
                "累积热量jg",
                "累计放热",
                "累积放热",
            },
        }

        rename_map = {}
        used_targets = set()
        for col in df.columns:
            key = self._column_key(col)
            for target, names in aliases.items():
                if target not in used_targets and self._matches_column(key, names):
                    rename_map[col] = target
                    used_targets.add(target)
                    break

        return df.rename(columns=rename_map)

    @staticmethod
    def _matches_column(key: str, aliases: set[str]) -> bool:
        if key in aliases:
            return True
        return any(alias and (alias in key or key in alias) for alias in aliases)

    @staticmethod
    def _column_key(column_name: object) -> str:
        key = str(column_name).strip().lower()
        key = re.sub(r"\([^)]*\)|（[^）]*）|\[[^]]*\]", "", key)
        key = key.replace("/", "_").replace("-", "_").replace("·", "_")
        return re.sub(r"[\s_]+", "", key)
