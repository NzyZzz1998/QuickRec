import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

UNKNOWN = "unknown"

SECTION_DEFAULT_KEYS = {
    "app": ("version", "python", "windows", "frozen"),
    "config": ("save_path", "diagnostic_dir", "audio_source", "quality", "fps"),
    "recorder": ("state", "mode", "output_path", "session_dir", "last_result"),
    "ffmpeg": ("path", "exists", "frozen"),
    "audio": ("requested_source", "final_source", "degraded", "reason"),
    "window": ("hwnd", "title", "mode", "stage", "reason", "rect", "foreground_result"),
}


@dataclass(frozen=True)
class DiagnosticDirectoryResult:
    ok: bool
    path: Path
    error: str = ""


@dataclass(frozen=True)
class DiagnosticExportResult:
    ok: bool
    path: Path | None = None
    error: str = ""


@dataclass(frozen=True)
class DiagnosticSnapshot:
    app: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    recorder: dict[str, Any] = field(default_factory=dict)
    ffmpeg: dict[str, Any] = field(default_factory=dict)
    audio: dict[str, Any] = field(default_factory=dict)
    window: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    recent_logs: list[str] = field(default_factory=list)


def _as_path(path: str | Path) -> Path:
    return path if isinstance(path, Path) else Path(str(path))


def _display(value: Any) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, str) and not value.strip():
        return UNKNOWN
    if isinstance(value, (list, tuple)) and not value:
        return UNKNOWN
    return str(value)


def resolve_diagnostic_dir(config, override_dir: str | Path | None = None) -> Path:
    """解析诊断目录，优先使用调用方传入目录。"""
    if override_dir:
        return _as_path(override_dir)
    if hasattr(config, "get_diagnostic_dir"):
        return Path(config.get_diagnostic_dir())
    save_path = config.get("save_path")
    return Path(save_path) / "QuickRecDiagnostics"


def ensure_diagnostic_dir(path: str | Path) -> DiagnosticDirectoryResult:
    """确保诊断目录存在。"""
    target = _as_path(path)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return DiagnosticDirectoryResult(False, target, str(exc))
    if not target.is_dir():
        return DiagnosticDirectoryResult(False, target, "path is not a directory")
    return DiagnosticDirectoryResult(True, target)


def is_diagnostic_dir_writable(path: str | Path) -> bool:
    """检查诊断目录是否可写。"""
    target = _as_path(path)
    result = ensure_diagnostic_dir(target)
    if not result.ok:
        return False
    probe = target / ".quickrec_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        try:
            probe.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def read_recent_log_lines(log_path: str | Path, max_lines: int = 100) -> list[str]:
    """读取最近日志行。"""
    path = _as_path(log_path)
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except Exception:
        return []


def initialize_file_logging(
    config,
    logger: logging.Logger,
    diagnostic_dir: str | Path | None = None,
    fallback_dir: str | Path | None = None,
) -> DiagnosticDirectoryResult:
    """初始化诊断文件日志，失败时降级到 fallback 目录。"""
    target = resolve_diagnostic_dir(config, diagnostic_dir)
    result = ensure_diagnostic_dir(target)
    used_fallback = False
    if not result.ok:
        fallback = _as_path(fallback_dir) if fallback_dir else Path(tempfile.gettempdir()) / "QuickRecDiagnostics"
        fallback_result = ensure_diagnostic_dir(fallback)
        if not fallback_result.ok:
            return fallback_result
        result = fallback_result
        used_fallback = True

    for handler in list(logger.handlers):
        if getattr(handler, "_quickrec_diagnostic_handler", False):
            logger.removeHandler(handler)
            handler.close()

    log_path = result.path / "quickrec.log"
    try:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
    except Exception as exc:
        return DiagnosticDirectoryResult(False, result.path, str(exc))
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    file_handler._quickrec_diagnostic_handler = True
    logger.addHandler(file_handler)
    if used_fallback:
        logger.warning(f"diagnostic directory fallback: {result.path}")
    return result


def _format_section(title: str, values: dict[str, Any]) -> list[str]:
    lines = [f"[{title}]"]
    keys = sorted(set(values) | set(SECTION_DEFAULT_KEYS.get(title, ())))
    if not keys:
        lines.append(f"{UNKNOWN}: {UNKNOWN}")
        return lines
    for key in keys:
        lines.append(f"{key}: {_display(values.get(key))}")
    return lines


def format_snapshot_text(snapshot: DiagnosticSnapshot) -> str:
    """将诊断快照格式化为纯文本。"""
    lines: list[str] = [
        "QuickRec Diagnostic Report",
        f"generated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    sections = [
        ("app", snapshot.app),
        ("config", snapshot.config),
        ("recorder", snapshot.recorder),
        ("ffmpeg", snapshot.ffmpeg),
        ("audio", snapshot.audio),
        ("window", snapshot.window),
    ]
    for title, values in sections:
        lines.extend(_format_section(title, values))
        lines.append("")

    lines.append("[errors]")
    lines.extend(snapshot.errors or [UNKNOWN])
    lines.append("")
    lines.append("[recent_logs]")
    lines.extend(snapshot.recent_logs or [UNKNOWN])
    lines.append("")
    return "\n".join(lines)


def export_diagnostic_file(
    text: str,
    diagnostic_dir: str | Path,
    now: datetime | None = None,
) -> DiagnosticExportResult:
    """导出 UTF-8 诊断文本文件。"""
    directory = _as_path(diagnostic_dir)
    result = ensure_diagnostic_dir(directory)
    if not result.ok:
        return DiagnosticExportResult(False, error=result.error)
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    path = directory / f"diagnostic_{timestamp}.txt"
    try:
        path.write_text(text, encoding="utf-8")
    except Exception as exc:
        return DiagnosticExportResult(False, error=str(exc))
    return DiagnosticExportResult(True, path=path)


def open_diagnostic_dir(path: str | Path) -> DiagnosticDirectoryResult:
    """使用系统文件管理器打开诊断目录。"""
    target = _as_path(path)
    result = ensure_diagnostic_dir(target)
    if not result.ok:
        return result
    try:
        os.startfile(str(target))
    except Exception as exc:
        return DiagnosticDirectoryResult(False, target, str(exc))
    return DiagnosticDirectoryResult(True, target)
