from pathlib import Path


def test_systemd_unit_has_required_directives() -> None:
    txt = Path("deploy/shift-scheduler.service").read_text(encoding="utf-8")
    assert "[Unit]" in txt
    assert "[Service]" in txt
    assert "[Install]" in txt
    assert "Restart=always" in txt
    assert "--port 2323" in txt
    assert "--host 127.0.0.1" in txt
    assert "--workers 1" in txt
    assert "EnvironmentFile=" in txt


def test_install_md_documents_steps() -> None:
    txt = Path("deploy/INSTALL.md").read_text(encoding="utf-8")
    for needle in [
        "set-password",
        "ADMIN_PASSWORD_HASH",
        "SESSION_SECRET",
        "alembic upgrade head",
        "systemctl",
        "Cloudflare",
    ]:
        assert needle in txt, f"Missing {needle!r} in INSTALL.md"


def test_readme_mentions_core_facts() -> None:
    txt = Path("README.md").read_text(encoding="utf-8")
    assert "shift" in txt.lower()
    assert "uv" in txt.lower()
    assert "2323" in txt
    assert "Hebrew" in txt or "RTL" in txt or "עברית" in txt
