import os
import pathlib
import subprocess
import tempfile


def test_alembic_upgrade_head_creates_all_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = pathlib.Path(td) / "mig.db"
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{db_path}"
        subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True, env=env)
        import sqlite3

        conn = sqlite3.connect(db_path)
        names = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        expected = {"person", "presence_period", "shift", "shift_assignment", "edit_log"}
        assert expected.issubset(names)
