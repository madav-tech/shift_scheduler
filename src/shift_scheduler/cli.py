import sys

import click

from shift_scheduler.auth import hash_password


@click.group()
def cli() -> None:
    """Shift Scheduler CLI."""


@cli.command("set-password")
@click.option("--password", default=None, help="Skip the prompt and use this value (CI use only).")
def set_password(password: str | None) -> None:
    """Hash a new admin password and print the env-var line to set."""
    if password is None:
        first = click.prompt("סיסמה חדשה", hide_input=True)
        confirm = click.prompt("אישור סיסמה", hide_input=True)
        if first != confirm:
            click.echo("הסיסמה אינה תואמת", err=True)
            sys.exit(2)
        password = first
    h = hash_password(password)
    click.echo("Add this line to your .env or systemd EnvironmentFile:")
    click.echo(f"ADMIN_PASSWORD_HASH={h}")


if __name__ == "__main__":
    cli()
