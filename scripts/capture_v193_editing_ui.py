"""生成 v1.9.3 剪辑工作台的离屏布局证据。"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PyQt5.QtGui import QFont  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from services.project_library import ProjectLibraryService  # noqa: E402
from services.timeline_session import TimelineSession  # noqa: E402
from ui.timeline_editor_window import TimelineEditorWindow  # noqa: E402
from utils.project_store import ProjectMaterialRef  # noqa: E402


def _build_session(root: Path) -> TimelineSession:
    service = ProjectLibraryService(
        root / "projects.json",
        default_root=root / "projects",
    )
    result = service.create_project(
        name="v1.9.3 剪辑界面布局验证",
        project_id="v193-ui-evidence",
    )
    if not result.ok:
        raise RuntimeError(result.error or "无法创建证据项目")
    project = service.get_project("v193-ui-evidence").project
    if project is None:
        raise RuntimeError("无法读取证据项目")

    durations = (12.0, 8.0, 16.0)
    for index, duration in enumerate(durations, start=1):
        media = root / f"中文 素材 {index}.mp4"
        media.write_bytes(b"quickrec-v193-ui-evidence")
        project.materials.append(
            ProjectMaterialRef(
                material_id=f"material-{index}",
                last_known_path=str(media),
                file_name=media.name,
                added_at=f"2026-07-29T10:0{index}:00+08:00",
                metadata_snapshot={
                    "duration_sec": duration,
                    "width": 1920,
                    "height": 1080,
                    "fps": 30.0,
                    "audio_source": "both" if index == 1 else "none",
                },
            )
        )
    saved = service.commit_project_candidate("v193-ui-evidence", project)
    if not saved.ok:
        raise RuntimeError(saved.error or "无法保存证据项目")

    session = TimelineSession(service, "v193-ui-evidence")
    for index in range(1, 4):
        added = session.commands.add_material(
            f"material-{index}",
            has_audio=index == 1,
        )
        if not added.ok:
            raise RuntimeError(added.error or "无法创建证据时间线")
    return session


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    app.setFont(QFont("Microsoft YaHei UI", 9))
    with tempfile.TemporaryDirectory(prefix="quickrec-v193-ui-") as temp_dir:
        session = _build_session(Path(temp_dir))
        window = TimelineEditorWindow()
        window.set_session(session)
        first_clip = session.timeline.clips[0]
        window._timeline_canvas.select_clip(first_clip.clip_id)
        window._on_clip_selected(first_clip.clip_id, first_clip.track_id)
        window._open_clip_inspector()
        window.show()

        for width, height in ((960, 640), (1216, 760), (1600, 900)):
            window.resize(width, height)
            app.processEvents()
            target = output_dir / f"timeline-editor-{width}x{height}.png"
            if not window.grab().save(str(target), "PNG"):
                raise RuntimeError(f"无法保存截图：{target}")
        window.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
