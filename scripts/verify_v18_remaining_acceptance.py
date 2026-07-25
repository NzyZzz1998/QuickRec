"""验证 QuickRec Full v1.8 剩余的可自动化验收链路。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sample-video", required=True)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    appdata = output_dir / "appdata"
    os.environ["APPDATA"] = str(appdata)
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root / "src"))

    from PyQt5.QtCore import QRect
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication

    from config import ConfigManager, ConfigSaveResult
    from services.capture_capability import (
        CapabilityCache,
        CapabilityCacheStore,
        CaptureCapabilityService,
        DisplayEnvironment,
        EnvironmentFingerprint,
    )
    from services.material_query import MaterialQueryCriteria, MaterialQueryEngine
    from services.recording_library import RecordingLibraryService
    from ui.material_library_dialog import MaterialLibraryDialog
    from ui.settings_dialog import SettingsDialog
    from ui.workbench_pages import DiagnosticPage
    from ui.workbench_window import WorkbenchWindow, clamp_workbench_geometry
    from utils.media_metadata import probe_media

    app = QApplication.instance() or QApplication([])
    report: dict[str, object] = {}

    config = ConfigManager()
    recordings_dir = output_dir / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    initial = config.snapshot()
    initial.update(
        save_path=str(recordings_dir),
        fps=30,
        quality="high",
        diagnostic_dir="",
        diagnostic_dir_customized=False,
    )
    require(config.save_candidate(initial).ok, "无法写入隔离配置")

    screen_rect = app.primaryScreen().availableGeometry()
    offscreen = {
        "x": screen_rect.right() + 5000,
        "y": screen_rect.bottom() + 5000,
        "width": 1200,
        "height": 760,
        "maximized": False,
    }
    clamped = clamp_workbench_geometry(offscreen, [QRect(screen_rect)])
    clamped_rect = QRect(
        int(clamped["x"]),
        int(clamped["y"]),
        int(clamped["width"]),
        int(clamped["height"]),
    )
    require(screen_rect.contains(clamped_rect), "离屏窗口未恢复到可见区域")
    window = WorkbenchWindow(saved_geometry=offscreen)
    window.show()
    app.processEvents()
    require(screen_rect.intersects(window.frameGeometry()), "工作台窗口不可见")
    window.grab().save(str(output_dir / "workbench-clamped.png"))
    report["workbench_geometry"] = {
        "screen": [
            screen_rect.x(),
            screen_rect.y(),
            screen_rect.width(),
            screen_rect.height(),
        ],
        "requested": offscreen,
        "clamped": clamped,
        "visible": True,
    }
    window.hide()

    settings = SettingsDialog(config, embedded=True)
    settings.show()
    settings._combo_fps.setCurrentText("60")
    require(settings.is_dirty, "设置修改后未进入草稿状态")
    require(settings.save_changes(), "设置保存失败")
    reloaded = ConfigManager()
    require(reloaded.get("fps") == 60, "设置重启后未保持")

    settings._combo_quality.setCurrentIndex(
        settings._combo_quality.findData("medium")
    )
    saved_quality = config.get("quality")
    failure = ConfigSaveResult(False, "write_temp", "受控写入失败")
    with patch.object(config, "save_candidate", return_value=failure):
        require(not settings.save_changes(), "受控保存失败被错误报告为成功")
    require(settings.is_dirty, "保存失败后草稿状态丢失")
    require(config.get("quality") == saved_quality, "保存失败污染正式配置")
    settings.grab().save(str(output_dir / "settings-save-failed.png"))
    report["settings"] = {
        "saved_fps": reloaded.get("fps"),
        "failure_kept_dirty": settings.is_dirty,
        "failure_preserved_quality": config.get("quality"),
        "failure_feedback": settings._label_save_status.text(),
    }
    settings.close()

    diagnostic = DiagnosticPage(config)
    diagnostic.show()
    diagnostic_dir = output_dir / "自定义 诊断目录"
    diagnostic._edit_diagnostic_dir.setText(str(diagnostic_dir))
    require(diagnostic.is_dirty, "诊断目录修改后未进入草稿状态")
    require(diagnostic.save_changes(), "诊断目录保存失败")
    diagnostic_reloaded = ConfigManager()
    require(
        Path(diagnostic_reloaded.get_diagnostic_dir()) == diagnostic_dir,
        "诊断目录重启后未保持",
    )
    diagnostic.grab().save(str(output_dir / "diagnostic-saved.png"))
    report["diagnostic"] = {
        "saved_directory": diagnostic_reloaded.get_diagnostic_dir(),
        "dirty_after_save": diagnostic.is_dirty,
        "feedback": diagnostic._status_label.text(),
    }
    diagnostic.close()

    sample_video = Path(args.sample_video).resolve()
    require(sample_video.is_file(), "受控样本视频不存在")
    metadata = probe_media(sample_video)
    require(metadata.ok, f"受控样本视频不可解析：{metadata.error}")
    library_path = output_dir / "recordings.json"
    library = RecordingLibraryService(library_path)

    paths: list[Path] = []
    for index, name in enumerate(
        (
            "QuickRec_中文 空格_全屏.mp4",
            "QuickRec_区域_筛选.mp4",
            "QuickRec_窗口_排序.mp4",
        ),
        start=1,
    ):
        target = recordings_dir / name
        shutil.copy2(sample_video, target)
        paths.append(target)
        added = library.add_recording(
            target,
            metadata={
                "mode": ("fullscreen", "region", "window")[index - 1],
                "audio_source": ("none", "system", "both")[index - 1],
                "duration_sec": float(metadata.duration_sec or 0) + index,
                "width": metadata.width,
                "height": metadata.height,
                "fps": metadata.fps,
            },
            diagnostic_dir=str(diagnostic_dir),
        )
        require(added.ok, f"素材 {index} 入库失败：{added.error}")

    query = MaterialQueryEngine().execute(
        library.load().items,
        [],
        MaterialQueryCriteria(
            keyword="窗口",
            mode="window",
            audio="both",
            sort_order="duration_desc",
        ),
    )
    require(len(query.formal_items) == 1, "素材组合查询结果不正确")
    require(query.formal_items[0].file_name == paths[2].name, "素材查询命中错误")

    material_page = MaterialLibraryDialog(library, embedded=True)
    material_page.show()
    material_page._search_input.setText("窗口")
    material_page._mode_combo.setCurrentIndex(
        material_page._mode_combo.findData("window")
    )
    material_page._audio_combo.setCurrentIndex(
        material_page._audio_combo.findData("both")
    )
    QTest.qWait(180)
    app.processEvents()
    require(material_page._table.rowCount() == 1, "素材界面组合筛选结果不正确")
    material_page._table.selectRow(0)
    material_page.grab().save(str(output_dir / "material-query.png"))

    selected = material_page._selected_item()
    require(selected is not None, "素材界面未选中查询结果")
    material_page._btn_copy.click()
    copied_path = app.clipboard().text()
    require(
        copied_path == selected.file_path,
        "复制路径未写入完整素材路径",
    )
    old_path = Path(selected.file_path)
    relocated_path = output_dir / "重新定位 目标" / old_path.name
    relocated_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(old_path, relocated_path)
    old_path.unlink()
    relinked = library.relink(selected.id, relocated_path)
    require(relinked.ok, f"素材重新定位失败：{relinked.error}")
    persisted = library.find_existing(item_id=selected.id)
    require(
        persisted is not None and Path(persisted.file_path) == relocated_path,
        "重新定位路径未持久化",
    )
    require(persisted.duration_sec is not None, "重新定位后时长缺失")
    require(persisted.width is not None and persisted.height is not None, "重新定位后分辨率缺失")
    require(persisted.fps is not None, "重新定位后 FPS 缺失")
    removed = library.remove(selected.id)
    require(removed.ok, f"仅移除索引失败：{removed.error}")
    require(relocated_path.exists(), "仅移除索引错误删除了视频")
    require(library.find_existing(item_id=selected.id) is None, "索引记录未移除")

    recycle_path = recordings_dir / "QuickRec_受控回收站验证.mp4"
    shutil.copy2(sample_video, recycle_path)
    recycled_added = library.add_recording(
        recycle_path,
        metadata={
            "mode": "fullscreen",
            "audio_source": "none",
            "duration_sec": metadata.duration_sec,
            "width": metadata.width,
            "height": metadata.height,
            "fps": metadata.fps,
        },
        diagnostic_dir=str(diagnostic_dir),
    )
    require(recycled_added.ok, f"回收站测试素材入库失败：{recycled_added.error}")
    recycle_item = library.find_existing(file_path=recycle_path)
    require(recycle_item is not None, "回收站测试素材未进入索引")
    recycled = library.recycle(recycle_item.id)
    require(recycled.ok, f"移入 Windows 回收站失败：{recycled.error}")
    require(not recycle_path.exists(), "回收站操作后测试视频仍位于原路径")
    require(
        library.find_existing(item_id=recycle_item.id) is None,
        "回收站操作后索引记录仍存在",
    )
    report["material_library"] = {
        "query_match": query.formal_items[0].file_name,
        "query_count": len(query.formal_items),
        "relinked_path": str(relocated_path),
        "relinked_metadata": {
            "duration_sec": persisted.duration_sec,
            "width": persisted.width,
            "height": persisted.height,
            "fps": persisted.fps,
        },
        "copied_path": copied_path,
        "remove_index_kept_video": relocated_path.exists(),
        "recycle_bin_removed_source": not recycle_path.exists(),
        "recycle_bin_removed_index": (
            library.find_existing(item_id=recycle_item.id) is None
        ),
        "remaining_items": len(library.load().items),
    }
    material_page.close()

    display = DisplayEnvironment(1, 1920, 1080, 120)
    base_fingerprint = EnvironmentFingerprint(
        monitor_count=1,
        width=1920,
        height=1080,
        refresh_hz=120,
        save_drive="E:",
        processor="CPU-A",
        graphics="GPU-A",
        ffmpeg_version="ffmpeg-A",
        encoder="libx264-superfast-yuv420p",
    )
    cache_store = CapabilityCacheStore(output_dir / "capture-capabilities.json")
    require(
        cache_store.save(
            CapabilityCache(
                passed=True,
                checked_at="2026-07-25T23:00:00+08:00",
                average_fps=119.5,
                minimum_one_second_fps=112,
                fingerprint=base_fingerprint,
            )
        ).ok,
        "能力缓存写入失败",
    )
    capability = CaptureCapabilityService(
        cache_store,
        runner=lambda *_args: (_ for _ in ()).throw(
            AssertionError("缓存验证不应运行自检")
        ),
    )
    require(
        capability.check_readiness(display, base_fingerprint).ready,
        "匹配环境未复用通过缓存",
    )
    invalidation_variants = {
        "refresh_hz": replace(base_fingerprint, refresh_hz=144),
        "resolution": replace(base_fingerprint, width=2560, height=1440),
        "save_drive": replace(base_fingerprint, save_drive="D:"),
        "processor": replace(base_fingerprint, processor="CPU-B"),
        "graphics": replace(base_fingerprint, graphics="GPU-B"),
        "ffmpeg": replace(base_fingerprint, ffmpeg_version="ffmpeg-B"),
        "encoder": replace(base_fingerprint, encoder="libx264-medium-yuv420p"),
    }
    invalidation_results = {
        name: capability.check_readiness(display, fingerprint).ready
        for name, fingerprint in invalidation_variants.items()
    }
    require(
        not any(invalidation_results.values()),
        "环境变化后存在未失效的能力缓存",
    )
    report["capture_capability"] = {
        "matching_cache_ready": True,
        "invalidation_ready_values": invalidation_results,
    }

    report_path = output_dir / "verification-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
