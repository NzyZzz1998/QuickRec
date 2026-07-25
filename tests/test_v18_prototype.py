import re
from pathlib import Path

PROTOTYPE_DIR = Path("doc/releases/v1.8/prototype")
HTML_PATH = PROTOTYPE_DIR / "index.html"
CSS_PATH = PROTOTYPE_DIR / "styles.css"
JS_PATH = PROTOTYPE_DIR / "app.js"
REFERENCE_DIR = PROTOTYPE_DIR / "reference"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v18_prototype_files_are_utf8_and_self_contained():
    for path in (HTML_PATH, CSS_PATH, JS_PATH):
        text = _read(path)
        assert "\ufffd" not in text
        assert not re.search(r"https?://", text)


def test_v18_prototype_contains_exactly_four_primary_pages():
    html = _read(HTML_PATH)
    pages = re.findall(r'<section[^>]+class="page[^"]*"[^>]+data-page-panel="([^"]+)"', html)

    assert pages == ["record", "library", "settings", "diagnostics"]


def test_v18_product_controls_have_development_contracts():
    html = _read(HTML_PATH)
    interactive_controls = re.findall(
        r"<(?:button|input|select|textarea)\b[^>]*>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    missing = [
        control
        for control in interactive_controls
        if "data-contract=" not in control
        and "data-prototype-control" not in control
        and 'type="hidden"' not in control
    ]

    assert not missing


def test_v18_static_contract_keys_have_javascript_definitions():
    html = _read(HTML_PATH)
    javascript = _read(JS_PATH)
    html_keys = set(re.findall(r'data-contract="([^"]+)"', html))
    javascript_keys = set(
        re.findall(r'^\s*"([^"]+)":\s*contract\(', javascript, flags=re.MULTILINE)
    )

    assert html_keys
    assert html_keys <= javascript_keys


def test_v18_prototype_covers_required_floating_states():
    html = _read(HTML_PATH)
    expected_states = {
        "area",
        "window",
        "countdown",
        "toolbar",
        "paused",
        "saving",
        "result",
        "result-failed",
    }
    actual_states = set(re.findall(r'data-floating-view="([^"]+)"', html))

    assert expected_states <= actual_states


def test_v18_window_picker_uses_dedicated_vertical_layout():
    html = _read(HTML_PATH)
    css = _read(CSS_PATH)

    assert 'class="window-picker-summary"' in html
    assert 'class="window-selection-hint"' in html
    assert html.count('class="window-size"') == 3
    assert ".window-picker.floating-view.is-visible" in css
    assert "grid-template-columns: 34px minmax(0, 1fr) auto 20px" in css


def test_v18_floating_toolbar_has_reviewable_state_transition():
    html = _read(HTML_PATH)
    css = _read(CSS_PATH)
    javascript = _read(JS_PATH)

    assert 'id="playFloatingDemo"' in html
    assert 'id="toolbarTransitionShell"' in html
    assert ".toolbar-transition-shell" in css
    assert "transition: width 280ms" in css
    assert ".record-toolbar > .toolbar-button:first-of-type" in css
    assert "margin-left: auto" in css
    assert "const toolbarWidths" in javascript
    assert "function playFloatingDemo()" in javascript


def test_v18_settings_footer_does_not_overlay_scrollable_content():
    css = _read(CSS_PATH)

    assert '[data-page-panel="settings"].is-active' in css
    assert "flex-direction: column" in css
    assert ".settings-scroll" in css
    assert "overflow-y: auto" in css
    assert ".settings-footer" in css
    assert "position: static" in css
    assert "flex: 0 0 60px" in css


def test_v18_prototype_supports_reproducible_review_query_parameters():
    javascript = _read(JS_PATH)

    assert "new URLSearchParams(window.location.search)" in javascript
    for parameter in ("page", "state", "floating", "embed"):
        assert f'urlParams.get("{parameter}")' in javascript


def test_v18_reference_images_are_valid_nonempty_png_files():
    expected_images = {
        "settings-current.png",
        "material-library-current.png",
        "material-library-empty-current.png",
        "material-library-missing-current.png",
        "material-library-pending-current.png",
        "material-library-error-current.png",
        "window-selector-current.png",
        "area-selector-current.png",
        "toolbar-countdown-current.png",
        "toolbar-recording-current.png",
        "toolbar-paused-current.png",
        "toolbar-saving-current.png",
        "toolbar-result-current.png",
        "tray-menu-structure-reference.png",
    }
    actual_images = {path.name for path in REFERENCE_DIR.glob("*.png")}

    assert expected_images <= actual_images
    for name in expected_images:
        payload = (REFERENCE_DIR / name).read_bytes()
        assert payload.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(payload) > 1_000
