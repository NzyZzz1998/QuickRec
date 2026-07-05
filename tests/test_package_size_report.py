import os
import tempfile
import unittest

from scripts.package_size_report import (
    ComponentSize,
    build_report,
    check_package_constraints,
    collect_component_sizes,
    format_size,
    top_dirs,
    top_files,
    tree_size,
)


def write_file(path: str, size: int) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as output:
        output.write(b"x" * size)


class TestPackageSizeReport(unittest.TestCase):
    def test_tree_size_sums_nested_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "a.bin"), 10)
            write_file(os.path.join(temp_dir, "nested", "b.bin"), 15)

            self.assertEqual(tree_size(temp_dir), 25)

    def test_top_files_returns_largest_files_first(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "small.bin"), 10)
            write_file(os.path.join(temp_dir, "nested", "large.bin"), 30)

            rows = top_files(temp_dir, limit=1)

        self.assertEqual(rows, [("nested/large.bin", 30)])

    def test_top_dirs_returns_largest_directories_first(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "cv2", "cv2.pyd"), 40)
            write_file(os.path.join(temp_dir, "PyQt5", "Qt5", "QtCore.dll"), 20)

            rows = top_dirs(temp_dir, limit=1)

        self.assertEqual(rows, [("cv2", 40)])

    def test_top_dirs_includes_nested_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "_internal", "cv2", "cv2.pyd"), 40)
            write_file(os.path.join(temp_dir, "_internal", "tiny", "a.bin"), 1)

            rows = top_dirs(temp_dir, limit=2)

        self.assertEqual(rows[0], ("_internal", 41))
        self.assertIn(("_internal/cv2", 40), rows)

    def test_collect_component_sizes_groups_known_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "ffmpeg", "ffmpeg.exe"), 50)
            write_file(os.path.join(temp_dir, "cv2", "cv2.pyd"), 40)
            write_file(os.path.join(temp_dir, "numpy", "core.pyd"), 30)
            write_file(os.path.join(temp_dir, "PyQt5", "Qt5", "QtCore.dll"), 20)
            write_file(os.path.join(temp_dir, "python312.dll"), 10)
            write_file(os.path.join(temp_dir, "PIL", "Image.pyc"), 5)
            write_file(os.path.join(temp_dir, "soundcard", "mediafoundation.pyc"), 4)
            write_file(os.path.join(temp_dir, "pystray", "_win32.pyc"), 3)

            components = collect_component_sizes(temp_dir)

        by_name = {component.name: component.size for component in components}
        self.assertEqual(by_name["FFmpeg"], 50)
        self.assertEqual(by_name["OpenCV/cv2"], 40)
        self.assertEqual(by_name["NumPy"], 30)
        self.assertEqual(by_name["Qt/PyQt5"], 20)
        self.assertEqual(by_name["Python runtime"], 10)
        self.assertEqual(by_name["PIL/Pillow"], 5)
        self.assertEqual(by_name["soundcard"], 4)
        self.assertEqual(by_name["pystray"], 3)

    def test_collect_component_sizes_ignores_pyinstaller_internal_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "_internal", "ffmpeg", "ffmpeg.exe"), 50)
            write_file(os.path.join(temp_dir, "_internal", "cv2", "cv2.pyd"), 40)

            components = collect_component_sizes(temp_dir)

        by_name = {component.name: component.size for component in components}
        self.assertEqual(by_name["FFmpeg"], 50)
        self.assertEqual(by_name["OpenCV/cv2"], 40)

    def test_build_report_contains_key_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "ffmpeg", "ffmpeg.exe"), 50)

            report = build_report(temp_dir, top_limit=1)

        self.assertIn("总体积", report)
        self.assertIn("Top 1 大文件", report)
        self.assertIn("组件体积", report)

    def test_format_size_uses_mb_for_large_values(self):
        self.assertEqual(format_size(1024 * 1024), "1.00 MB")

    def test_component_size_is_orderable_by_size(self):
        components = [ComponentSize("small", 1), ComponentSize("large", 2)]

        self.assertEqual(sorted(components, reverse=True)[0].name, "large")

    def test_check_package_constraints_accepts_stable_v1_4_package_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "_internal", "ffmpeg", "ffmpeg.exe"), 50)
            write_file(os.path.join(temp_dir, "_internal", "cv2", "cv2.pyd"), 40)
            write_file(os.path.join(temp_dir, "QuickRec.exe"), 10)

            result = check_package_constraints(temp_dir, max_size_mb=1)

        self.assertTrue(result.ok)

    def test_check_package_constraints_rejects_missing_bundled_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "_internal", "cv2", "cv2.pyd"), 40)

            result = check_package_constraints(temp_dir, max_size_mb=1)

        self.assertFalse(result.ok)
        self.assertIn("ffmpeg", result.message)

    def test_check_package_constraints_rejects_removed_cv2(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "_internal", "ffmpeg", "ffmpeg.exe"), 50)

            result = check_package_constraints(temp_dir, max_size_mb=1)

        self.assertFalse(result.ok)
        self.assertIn("cv2", result.message)

    def test_check_package_constraints_rejects_opencv_videoio_ffmpeg_dll(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "_internal", "ffmpeg", "ffmpeg.exe"), 50)
            write_file(os.path.join(temp_dir, "_internal", "cv2", "cv2.pyd"), 40)
            write_file(os.path.join(temp_dir, "_internal", "opencv_videoio_ffmpeg4130_64.dll"), 30)

            result = check_package_constraints(temp_dir, max_size_mb=1)

        self.assertFalse(result.ok)
        self.assertIn("opencv_videoio_ffmpeg", result.message)

    def test_check_package_constraints_rejects_test_resources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_file(os.path.join(temp_dir, "_internal", "ffmpeg", "ffmpeg.exe"), 50)
            write_file(os.path.join(temp_dir, "_internal", "cv2", "cv2.pyd"), 40)
            write_file(os.path.join(temp_dir, "_internal", "tests", "test_app.py"), 10)

            result = check_package_constraints(temp_dir, max_size_mb=1)

        self.assertFalse(result.ok)
        self.assertIn("test resources", result.message)


if __name__ == "__main__":
    unittest.main()
