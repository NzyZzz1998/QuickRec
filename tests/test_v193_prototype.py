import re
from pathlib import Path

PROTOTYPE_DIR = Path("doc/releases/v1.9.3/prototype")
HTML_PATH = PROTOTYPE_DIR / "index.html"
CSS_PATH = PROTOTYPE_DIR / "styles.css"
TIMELINE_CSS_PATH = PROTOTYPE_DIR / "timeline.css"
JS_PATH = PROTOTYPE_DIR / "app.js"
TIMELINE_JS_PATH = PROTOTYPE_DIR / "timeline.js"
DESIGN_PATH = PROTOTYPE_DIR / "prototype-design.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v193_prototype_files_are_utf8_and_self_contained() -> None:
    for path in (
        HTML_PATH,
        CSS_PATH,
        TIMELINE_CSS_PATH,
        JS_PATH,
        TIMELINE_JS_PATH,
        DESIGN_PATH,
    ):
        text = _read(path)
        assert "\ufffd" not in text
        assert not re.search(r"https?://", text)


def test_v193_prototype_identifies_the_correct_version_and_scope() -> None:
    html = _read(HTML_PATH)
    design = _read(DESIGN_PATH)

    assert "QuickRec Full v1.9.3" in html
    assert "基础剪辑" in html
    assert "全局波纹" in html
    assert "QuickRec Full v1.9.3" in design
    assert "v1.9.2 可播放多轨时间线原型" not in html


def test_v193_prototype_keeps_the_complete_workbench_pages() -> None:
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


def test_v193_product_controls_have_development_contracts() -> None:
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
    assert html.count('class="clip-trim-handle') == 2
    assert 'data-contract="timeline.trim-handle-in"' in html
    assert 'data-contract="timeline.trim-handle-out"' in html


def test_v193_all_static_contract_references_are_defined() -> None:
    html = _read(HTML_PATH)
    javascript = _read(JS_PATH) + _read(TIMELINE_JS_PATH)
    used = set(re.findall(r'data-contract="([^"]+)"', html))
    defined = set(re.findall(r'"([^"]+)":\s*contract\(', javascript))

    assert not used - defined


def test_v193_prototype_covers_editing_and_ripple_controls() -> None:
    html = _read(HTML_PATH)
    javascript = _read(TIMELINE_JS_PATH)

    for control_id in (
        "splitClipAtPlayhead",
        "deleteTimelineClip",
        "toggleClipInspector",
        "trimSourceIn",
        "trimSourceOut",
        "applyTrimValues",
        "cancelTrimValues",
    ):
        assert f'id="{control_id}"' in html

    for contract_name in (
        "timeline.trim-handle-in",
        "timeline.trim-handle-out",
        "timeline.trim-source-in",
        "timeline.trim-source-out",
        "timeline.trim-apply",
        "timeline.trim-cancel",
        "timeline.split",
        "timeline.ripple-delete",
        "timeline.ripple-confirm",
        "timeline.ripple-locate",
        "timeline.track-lock",
    ):
        assert contract_name in javascript


def test_v193_global_ripple_is_fixed_not_a_mode_toggle() -> None:
    html = _read(HTML_PATH)
    design = _read(DESIGN_PATH)

    assert 'class="ripple-mode-chip"' in html
    assert "固定“全局波纹”状态" in design
    assert 'id="toggleRippleMode"' not in html
    assert "非波纹模式" in design


def test_v193_prototype_covers_required_editing_states() -> None:
    html = _read(HTML_PATH)

    for state in (
        "timeline-trimming",
        "timeline-ripple-preview",
        "timeline-ripple-conflict",
        "timeline-track-locked",
        "timeline-save-rollback",
    ):
        assert f'value="{state}"' in html


def test_v193_cancel_action_is_kept_at_the_right_edge() -> None:
    app_js = _read(JS_PATH)
    timeline_js = _read(TIMELINE_JS_PATH)

    assert 'button.classList.add("is-cancel-action")' in app_js
    assert ".is-cancel-action" in _read(CSS_PATH)
    assert 'label: "取消"' in timeline_js
    assert 'contract: "modal.cancel"' in timeline_js


def test_v193_timeline_data_boundary_is_schema_v2() -> None:
    html = _read(HTML_PATH)
    design = _read(DESIGN_PATH)

    assert "schema v2" in html
    assert "时间线扩展升级为 schema v2" in design
    assert "source_start_us" in design
    assert "TimelineTrack.locked" in design
