import pandas as pd
from pathlib import Path
from utils.exceptions import DataParserError
from core.data_models import HydrationData
from utils.logger import logger


class CalorimetryParser:
    def __init__(self, sample_mass_g: float = 1.0) -> None:
        self.sample_mass_g = sample_mass_g

    def parse(self, file_path: Path) -> HydrationData:
        if not file_path.exists():
            raise DataParserError(f"目标文件不存在: {file_path.absolute()}")

        try:
            # NOTE: 根据文件扩展名动态路由解析引擎，兼顾 CSV 编码回退与 Excel 兼容性
            suffix = file_path.suffix.lower()
            if suffix == '.csv':
                try:
                    df = pd.read_csv(file_path, encoding='utf-8')
                except UnicodeDecodeError:
                    # NOTE: 捕获由于 Windows/国内仪器默认导出 ANSI/GBK 格式导致的解码失败，执行降级解析
                    logger.warning(f"UTF-8 解码失败，回退至 GB18030 解析: {file_path.name}")
                    df = pd.read_csv(file_path, encoding='gb18030')
            elif suffix in ['.xlsx', '.xls']:
                # NOTE: 读取 Excel 依赖 openpyxl 或 xlrd 库
                df = pd.read_excel(file_path)
            else:
                raise DataParserError(f"不支持的文件格式: {suffix}。仅支持 .csv, .xlsx, .xls")

            # 动态表头映射与修正
            column_mapping = {
                'time_h': 'time_h',
                'heat_flow_': 'heat_flow_mw',
                'heat_flow_mw': 'heat_flow_mw',
                'cumulative': 'cumulative_heat_j',
                'cumulative_heat_j': 'cumulative_heat_j'
            }
            df.rename(columns=column_mapping, inplace=True)

            target_cols = ['time_h', 'heat_flow_mw', 'cumulative_heat_j']
            for col in target_cols:
                if col not in df.columns:
                    raise DataParserError(f"数据表缺少关键列: {col}。请确认表头。")

            # 防御性类型转换与脏数据剔除
            for col in target_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df.dropna(subset=target_cols, inplace=True)

            if df.empty:
                raise DataParserError("数据清洗后为空，请检查文件内容是否全为有效数值。")

            # 物理归一化
            df['heat_flow_mw_g'] = df['heat_flow_mw'] / self.sample_mass_g
            df['cumulative_heat_j_g'] = df['cumulative_heat_j'] / self.sample_mass_g

            logger.info(f"数据加载成功: {file_path.name} (解析引擎: {suffix})")

            return HydrationData(
                time_h=df['time_h'].values,
                heat_flow_mw_g=df['heat_flow_mw_g'].values,
                cumulative_heat_j_g=df['cumulative_heat_j_g'].values
            )
        except DataParserError:
            raise
        except ImportError as e:
            logger.error(f"底层依赖缺失: {e}")
            raise DataParserError("无法读取 Excel 文件，请确保已安装 openpyxl。")
        except Exception as e:
            logger.error(f"解析器严重异常: {e}")
            raise DataParserError(f"数据解析遭遇未知失败: {str(e)}")