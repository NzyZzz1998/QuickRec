from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.product_identity import (
    AUTOSTART_NAME,
    CONFIG_DIR_NAME,
    DISPLAY_NAME,
    EXECUTABLE_NAME,
    NOTIFICATION_APP_ID,
    PACKAGE_DIR_NAME,
    PRODUCT_ID,
    TEMP_DIR_NAME,
    default_save_path,
    lite_appdata_dir,
    lite_temp_dir,
)
from version import APP_VERSION


def test_lite_identity_is_distinct_and_versioned() -> None:
    assert PRODUCT_ID == "QuickRec.Lite"
    assert DISPLAY_NAME == "QuickRec Lite"
    assert EXECUTABLE_NAME == "QuickRec-Lite.exe"
    assert PACKAGE_DIR_NAME == "QuickRec-Lite"
    assert AUTOSTART_NAME == "QuickRec Lite"
    assert NOTIFICATION_APP_ID == "QuickRec.Lite"
    assert APP_VERSION == "v0.1"


def test_lite_paths_use_independent_directory_names(tmp_path: Path) -> None:
    assert CONFIG_DIR_NAME == "QuickRec-Lite"
    assert TEMP_DIR_NAME == "QuickRec-Lite"
    assert lite_appdata_dir(tmp_path) == tmp_path / "QuickRec-Lite"
    assert lite_temp_dir(tmp_path) == tmp_path / "QuickRec-Lite"
    assert default_save_path(tmp_path) == tmp_path / "Videos" / "QuickRec Lite"


def test_lite_identity_does_not_reuse_full_runtime_names() -> None:
    runtime_names = {
        PRODUCT_ID,
        CONFIG_DIR_NAME,
        TEMP_DIR_NAME,
        AUTOSTART_NAME,
        NOTIFICATION_APP_ID,
        PACKAGE_DIR_NAME,
    }
    assert "QuickRec.Full" not in runtime_names
    assert os.path.basename(EXECUTABLE_NAME) != "QuickRec.exe"
