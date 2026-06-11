"""
文件命名模块

生成录制文件的文件名，格式: QuickRec_YYYYMMDD_HHmmss.mp4
同名时自动追加序号避免冲突。
"""

import os
from datetime import datetime
from pathlib import Path


class FileNamer:
    """文件命名器"""

    @staticmethod
    def generate(save_dir: str, prefix: str = "QuickRec") -> str:
        """
        生成录制文件路径

        Args:
            save_dir: 保存目录
            prefix: 文件名前缀

        Returns:
            完整的文件路径，如 C:/Videos/QuickRec/QuickRec_20260611_143025.mp4
        """
        # 确保目录存在
        os.makedirs(save_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{prefix}_{timestamp}"

        # 检查冲突，追加序号
        filepath = Path(save_dir) / f"{base}.mp4"
        if not filepath.exists():
            return str(filepath)

        # 有冲突，追加序号
        counter = 1
        while True:
            filepath = Path(save_dir) / f"{base}_{counter:03d}.mp4"
            if not filepath.exists():
                return str(filepath)
            counter += 1
