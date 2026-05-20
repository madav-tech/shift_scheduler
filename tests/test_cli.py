from click.testing import CliRunner

from shift_scheduler.auth import verify_password
from shift_scheduler.cli import cli


def test_set_password_prompts_and_prints_env_line() -> None:
    runner = CliRunner()
    r = runner.invoke(cli, ["set-password"], input="hunter2\nhunter2\n")
    assert r.exit_code == 0
    out = r.output
    assert "ADMIN_PASSWORD_HASH=" in out
    line = next(line for line in out.splitlines() if line.startswith("ADMIN_PASSWORD_HASH="))
    h = line.split("=", 1)[1].strip()
    assert h.startswith("$argon2")
    assert verify_password(h, "hunter2") is True


def test_set_password_mismatch_exits_nonzero() -> None:
    runner = CliRunner()
    r = runner.invoke(cli, ["set-password"], input="aaa\nbbb\n")
    assert r.exit_code != 0
    assert "אינה תואמת" in r.output or "do not match" in r.output


def test_module_main_dispatches() -> None:
    import shift_scheduler.__main__ as m
    assert hasattr(m, "cli")
