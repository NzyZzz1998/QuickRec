from __future__ import annotations

import argparse
import os
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class ComponentSize:
    size: int
    name: str

    def __init__(self, name: str, size: int):
        object.__setattr__(self, "size", size)
        object.__setattr__(self, "name", name)


@dataclass(frozen=True)
class PackageConstraintResult:
    ok: bool
    message: str


def _to_posix(path: str) -> str:
    return path.replace(os.sep, "/")


def format_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.2f} MB"
    if size >= 1024:
        return f"{size / 1024:.2f} KB"
    return f"{size} B"


def tree_size(path: str) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                total += os.path.getsize(file_path)
            except OSError:
                continue
    return total


def top_files(path: str, limit: int = 20) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for root, _, files in os.walk(path):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                size = os.path.getsize(file_path)
            except OSError:
                continue
            rows.append((_to_posix(os.path.relpath(file_path, path)), size))
    return sorted(rows, key=lambda row: row[1], reverse=True)[:limit]


def top_dirs(path: str, limit: int = 20) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for root, dirs, _ in os.walk(path):
        for dirname in dirs:
            dir_path = os.path.join(root, dirname)
            rows.append((_to_posix(os.path.relpath(dir_path, path)), tree_size(dir_path)))
    return sorted(rows, key=lambda row: row[1], reverse=True)[:limit]


def _component_for(relative_path: str) -> str:
    lowered = relative_path.lower()
    if lowered.startswith("_internal/"):
        lowered = lowered[len("_internal/"):]
    first = lowered.split("/", 1)[0]
    if lowered.startswith("ffmpeg/") or first == "ffmpeg.exe":
        return "FFmpeg"
    if first == "cv2" or lowered.endswith(".pyd") and "cv2" in lowered:
        return "OpenCV/cv2"
    if first == "numpy" or first == "numpy.libs":
        return "NumPy"
    if first == "pyqt5" or "qt5" in lowered or lowered.startswith("platforms/"):
        return "Qt/PyQt5"
    if first == "pil" or first == "pillow.libs":
        return "PIL/Pillow"
    if first == "soundcard":
        return "soundcard"
    if first == "pystray":
        return "pystray"
    if first.startswith("python") or first in {"base_library.zip", "libcrypto-3.dll", "libssl-3.dll"}:
        return "Python runtime"
    return "Other"


def collect_component_sizes(path: str) -> list[ComponentSize]:
    sizes: dict[str, int] = {}
    for root, _, files in os.walk(path):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                size = os.path.getsize(file_path)
            except OSError:
                continue
            relative_path = _to_posix(os.path.relpath(file_path, path))
            component = _component_for(relative_path)
            sizes[component] = sizes.get(component, 0) + size
    return sorted((ComponentSize(name, size) for name, size in sizes.items()), reverse=True)


def _find_matching_files(path: str, needle: str) -> list[str]:
    matches: list[str] = []
    needle_lower = needle.lower()
    for root, _, files in os.walk(path):
        for filename in files:
            relative_path = _to_posix(os.path.relpath(os.path.join(root, filename), path))
            if needle_lower in relative_path.lower():
                matches.append(relative_path)
    return matches


def _find_matching_dirs(path: str, names: set[str]) -> list[str]:
    matches: list[str] = []
    names_lower = {name.lower() for name in names}
    for root, dirs, _ in os.walk(path):
        for dirname in dirs:
            if dirname.lower() in names_lower:
                matches.append(_to_posix(os.path.relpath(os.path.join(root, dirname), path)))
    return matches


def check_package_constraints(path: str, max_size_mb: int = 300) -> PackageConstraintResult:
    absolute_path = os.path.abspath(path)
    if not os.path.isdir(absolute_path):
        return PackageConstraintResult(False, f"dist directory missing: {absolute_path}")

    total_size = tree_size(absolute_path)
    max_size = max_size_mb * 1024 * 1024
    if total_size > max_size:
        return PackageConstraintResult(False, f"package too large: {format_size(total_size)} > {max_size_mb} MB")

    ffmpeg_matches = _find_matching_files(absolute_path, "ffmpeg/ffmpeg.exe")
    if not ffmpeg_matches:
        return PackageConstraintResult(False, "bundled ffmpeg missing")

    cv2_matches = _find_matching_files(absolute_path, "cv2.pyd")
    if not cv2_matches:
        return PackageConstraintResult(False, "cv2 missing")

    opencv_videoio_matches = _find_matching_files(absolute_path, "opencv_videoio_ffmpeg")
    if opencv_videoio_matches:
        return PackageConstraintResult(
            False,
            f"opencv_videoio_ffmpeg should be excluded: {', '.join(opencv_videoio_matches)}",
        )

    test_dirs = _find_matching_dirs(absolute_path, {"test", "tests", "__pycache__"})
    if test_dirs:
        return PackageConstraintResult(False, f"test resources should be excluded: {', '.join(test_dirs)}")

    return PackageConstraintResult(True, "package constraints ok")


def _table(rows: list[tuple[str, int]]) -> str:
    lines = ["| 路径 | 体积 |", "| --- | ---: |"]
    for name, size in rows:
        lines.append(f"| `{name}` | {format_size(size)} |")
    return "\n".join(lines)


def _component_table(rows: list[ComponentSize]) -> str:
    lines = ["| 组件 | 体积 |", "| --- | ---: |"]
    for row in rows:
        lines.append(f"| {row.name} | {format_size(row.size)} |")
    return "\n".join(lines)


def build_report(path: str, top_limit: int = 20) -> str:
    absolute_path = os.path.abspath(path)
    total = tree_size(absolute_path)
    constraints = check_package_constraints(absolute_path)
    return "\n\n".join(
        [
            "# QuickRec 打包体积分析",
            f"- 分析目录：`{absolute_path}`",
            f"- 总体积：{format_size(total)}",
            f"- v1.4 稳定性约束：{'通过' if constraints.ok else '失败'}，{constraints.message}",
            f"## Top {top_limit} 大文件\n{_table(top_files(absolute_path, top_limit))}",
            f"## Top {top_limit} 大目录\n{_table(top_dirs(absolute_path, top_limit))}",
            f"## 组件体积\n{_component_table(collect_component_sizes(absolute_path))}",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report QuickRec PyInstaller package size.")
    parser.add_argument("--dist", default=os.path.join("dist", "QuickRec"), help="PyInstaller output directory.")
    parser.add_argument("--top", type=int, default=20, help="Number of top files and directories to show.")
    parser.add_argument("--output", default="", help="Optional markdown report path.")
    parser.add_argument("--check", action="store_true", help="Fail if v1.4 package constraints are not met.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.dist, top_limit=args.top)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as output:
            output.write(report)
            output.write("\n")
    print(report)
    if args.check:
        constraints = check_package_constraints(args.dist)
        if not constraints.ok:
            print(f"FAILED: {constraints.message}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
