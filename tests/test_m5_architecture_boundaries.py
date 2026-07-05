import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


PROJECT_ROOT = Path(__file__).parent.parent


class TestM5ArchitectureBoundaries(unittest.TestCase):
    def _parse(self, relative_path: str) -> ast.AST:
        return ast.parse((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))

    def _imports(self, relative_path: str) -> set[str]:
        tree = self._parse(relative_path)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        return imports

    def _attribute_names(self, relative_path: str) -> set[str]:
        tree = self._parse(relative_path)
        return {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }

    def test_main_and_ui_do_not_import_m5_recorder_implementation_details(self):
        forbidden = {
            "recorder.window_diagnostics",
            "recorder.audio_preflight",
        }
        files = ["src/main.py", *[str(path.relative_to(PROJECT_ROOT)) for path in (PROJECT_ROOT / "src/ui").glob("*.py")]]

        for file in files:
            with self.subTest(file=file):
                self.assertTrue(self._imports(file).isdisjoint(forbidden))

    def test_main_and_ui_do_not_access_m5_private_recorder_fields(self):
        forbidden_attrs = {
            "_last_window_diagnostic",
            "_audio_preflight",
        }
        files = ["src/main.py", *[str(path.relative_to(PROJECT_ROOT)) for path in (PROJECT_ROOT / "src/ui").glob("*.py")]]

        for file in files:
            with self.subTest(file=file):
                self.assertTrue(self._attribute_names(file).isdisjoint(forbidden_attrs))


if __name__ == "__main__":
    unittest.main()
