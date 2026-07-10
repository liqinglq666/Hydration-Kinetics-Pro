from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import pandas as pd

from core.data_models import HydrationData
from utils.exceptions import DataParserError
from utils.logger import logger

InputMode = Literal["total", "normalized"]


class CalorimetryParser:
    def __init__(self, sample_mass_g: float = 1.0, input_mode: InputMode = "total") -> None:
        self.sample_mass_g = float(sample_mass_g)
        self.input_mode = input_mode

    def parse(self, file_path: Path) -> HydrationData:
        file_path = Path(file_path)
        if not file_path.exists():
            raise DataParserError(f"目标文件不存在: {file_path.absolute()}")
        if self.sample_mass_g <= 0:
            raise DataParserError("样品质量必须大于 0 g。")
        if self.input_mode not in {"total", "normalized"}:
            raise DataParserError("输入单位模式非法。请选择 total 或 normalized。")

        parser_warnings: list[str] = []
        try:
            suffix = file_path.suffix.lower()
            if suffix == ".csv":
                df = self._read_csv(file_path)
            elif suffix == ".xlsx":
                df = pd.read_excel(file_path)
            else:
                raise DataParserError("当前仅支持 .csv 和 .xlsx；旧式 .xls 请先另存为 .xlsx。")

            detected_mode = self._detect_unit_mode_from_headers(df.columns)
            if detected_mode and detected_mode != self.input_mode:
                raise DataParserError(
                    "表头单位与 GUI 选择冲突："
                    f"表头识别为 {detected_mode}，当前选择为 {self.input_mode}。"
                    "请改正单位模式后再计算。"
                )

            df = self._normalize_columns(df)
            target_cols = ["time_h", "heat_flow", "cumulative_heat"]
            missing = [column for column in target_cols if column not in df.columns]
            if missing:
                raise DataParserError(
                    f"数据表缺少关键列: {', '.join(missing)}。请确认表头包含时间、热流和累计热量。"
                )

            for column in target_cols:
                df[column] = pd.to_numeric(df[column], errors="coerce")
            df = df.dropna(subset=target_cols).sort_values("time_h")
            df = df.drop_duplicates(subset="time_h", keep="first")

            if df.empty:
                raise DataParserError("数据清洗后为空，请检查文件内容是否为有效数值。")
            if len(df) < 2 or not df["time_h"].is_monotonic_increasing:
                raise DataParserError("时间列必须包含至少两个递增的数据点。")

            if df["time_h"].iloc[0] < 0:
                warning = "检测到负时间点，请确认仪器基线设置。"
                parser_warnings.append(warning)
                logger.warning(warning)

            if self.input_mode == "total":
                heat_flow = df["heat_flow"] / self.sample_mass_g
                cumulative_heat = df["cumulative_heat"] / self.sample_mass_g
            else:
                heat_flow = df["heat_flow"]
                cumulative_heat = df["cumulative_heat"]

            logger.info("数据加载成功: %s", file_path.name)
            return HydrationData(
                time_h=df["time_h"].to_numpy(dtype=float),
                heat_flow_mw_g=heat_flow.to_numpy(dtype=float),
                cumulative_heat_j_g=cumulative_heat.to_numpy(dtype=float),
                input_mode=self.input_mode,
                detected_unit_mode=detected_mode,
                sample_mass_g=self.sample_mass_g,
                parser_warnings=parser_warnings,
            )
        except DataParserError:
            raise
        except ImportError as exc:
            raise DataParserError("无法读取 Excel 文件，请确认已安装 openpyxl。") from exc
        except Exception as exc:
            logger.error("解析器异常: %s", exc)
            raise DataParserError(f"数据解析失败: {exc}") from exc

    def _read_csv(self, file_path: Path) -> pd.DataFrame:
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return pd.read_csv(file_path, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise DataParserError(f"无法识别 CSV 文件编码: {file_path.name}")

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        aliases = {
            "time_h": {
                "time_h", "time", "timeh", "timehour", "timehours", "elapsedtime",
                "elapsedtimeh", "时间", "时间h", "时间小时",
            },
            "heat_flow": {
                "heat_flow", "heat_flow_mw", "heat_flow_mw_g", "heatflow",
                "heatflowmw", "heatflowmwg", "power", "powermw", "热流",
                "热流mw", "热流mwg", "放热速率", "放热速率mw", "放热速率mwg",
            },
            "cumulative_heat": {
                "cumulative", "cumulative_heat", "cumulative_heat_j",
                "cumulative_heat_j_g", "cumulativeheat", "cumulativeheatj",
                "cumulativeheatjg", "totalheat", "totalheatj", "累计热量",
                "累积热量", "累计热量jg", "累积热量jg", "累计放热", "累积放热",
            },
        }

        rename_map = {}
        used_targets = set()
        for column in df.columns:
            key = self._column_key(column)
            for target, names in aliases.items():
                if target not in used_targets and self._matches_column(key, names):
                    rename_map[column] = target
                    used_targets.add(target)
                    break
        return df.rename(columns=rename_map)

    @staticmethod
    def _detect_unit_mode_from_headers(columns) -> InputMode | None:
        normalized_hits = 0
        total_hits = 0
        for column in columns:
            raw = str(column).strip().lower()
            key = CalorimetryParser._column_key(raw)
            looks_like_heat = any(
                token in key
                for token in ("heat", "flow", "power", "热流", "放热", "热量", "累计", "累积")
            )
            if not looks_like_heat:
                continue

            if any(
                token in raw
                for token in ("mw/g", "mw g-1", "mw·g-1", "mw g^-1", "j/g", "j g-1", "j·g-1", "j g^-1")
            ):
                normalized_hits += 1
            elif any(token in key for token in ("mwg", "jg")):
                normalized_hits += 1
            elif any(token in key for token in ("mw", "j")):
                total_hits += 1

        if normalized_hits > 0:
            return "normalized"
        if total_hits >= 2:
            return "total"
        return None

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
