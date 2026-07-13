"""将受控文件移入系统回收站。"""

import logging
from dataclasses import dataclass
from pathlib import Path

from send2trash import send2trash

logger = logging.getLogger("QuickRec")


@dataclass(frozen=True)
class RecycleResult:
    ok: bool
    path: Path
    error: str = ""


def recycle_file(file_path: str | Path) -> RecycleResult:
    path = Path(file_path)
    if not path.is_file():
        logger.warning("recycle rejected missing file: %s", path)
        return RecycleResult(False, path, "file does not exist")
    try:
        send2trash(str(path))
    except OSError as exc:
        logger.warning("recycle failed: path=%s error=%s", path, exc)
        return RecycleResult(False, path, str(exc))
    logger.info("file moved to recycle bin: %s", path)
    return RecycleResult(True, path)
