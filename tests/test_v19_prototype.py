import re
from pathlib import Path

PROTOTYPE_DIR = Path("doc/releases/v1.9/prototype")
HTML_PATH = PROTOTYPE_DIR / "index.html"
CSS_PATH = PROTOTYPE_DIR / "styles.css"
JS_PATH = PROTOTYPE_DIR / "app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v19_prototype_files_are_utf8_and_self_contained():
    for path in (HTML_PATH, CSS_PATH, JS_PATH):
        text = _read(path)
        assert "\ufffd" not in text
        assert not re.search(r"https?://", text)


def test_v19_prototype_contains_exactly_five_primary_pages():
    pages = re.findall(
        r'<section[^>]+class="page[^"]*"[^>]+data-page-panel="([^"]+)"',
        _read(HTML_PATH),
    )

    assert pages == [
        "record",
        "library",
        "projects",
        "settings",
        "diagnostics",
    ]


def test_v19_product_controls_have_nearby_development_contracts():
    html = _read(HTML_PATH)
    controls = re.findall(
        r"<(?:button|input|select|textarea)\b[^>]*>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    missing = [
        control
        for control in controls
        if "data-contract=" not in control
        and "data-prototype-control" not in control
        and 'type="hidden"' not in control
    ]

    assert not missing


def test_v19_prototype_covers_project_lifecycle_and_equal_recording_modes():
    html = _read(HTML_PATH)
    javascript = _read(JS_PATH)

    for contract in (
        "projects.create",
        "projects.open",
        "projects.rename",
        "projects.archive",
        "projects.restore",
        "projects.delete",
        "projects.record-fullscreen",
        "projects.record-region",
        "projects.record-window",
    ):
        assert contract in html or contract in javascript
    assert "mode-card is-selected" not in html
    assert javascript.count("projects.record-") >= 3
