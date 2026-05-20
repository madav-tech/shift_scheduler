from pathlib import Path


def test_sidebar_js_uses_local_storage_key() -> None:
    p = Path("src/shift_scheduler/static/js/sidebar.js")
    src = p.read_text(encoding="utf-8")
    assert "localStorage" in src
    assert "ss-sidebar-collapsed" in src
    assert "sidebar-toggle" in src
