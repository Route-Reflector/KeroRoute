from rich.console import Console
from rich.panel import Panel
from datetime import datetime

from utils import load_sys_config


def get_style() -> str:
        return load_sys_config().get("user_interface", {}).get("message_style", "plain")


style = get_style()
_console = Console()



def _timestamp() -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S')}.{int(now.microsecond / 1000):03d}]"


def print_info(message: str):
    if style == "panel":
        _console.print(Panel(f"[bright_cyan]{_timestamp()} 🪧[INFO] {message}[/bright_cyan]"))
    else:
        _console.print(f"[bright_cyan]{_timestamp()} 🪧[INFO] {message}[/bright_cyan]")


def print_success(message: str):
    if style == "panel":
        _console.print(Panel(f"[bright_green]{_timestamp()} 💯[SUCCESS] {message}[/bright_green]"))
    else:
        _console.print(f"[bright_green]{_timestamp()} 💯[SUCCESS] {message}[/bright_green]")


def print_warning(message: str):
    if style == "panel":
        _console.print(Panel(f"[bright_yellow]{_timestamp()} 🚧[WARNING] {message}[/bright_yellow]"))
    else:
        _console.print(f"[bright_yellow]{_timestamp()} 🚧[WARNING] {message}[/bright_yellow]")


def print_error(message: str):
    if style == "panel":
        _console.print(Panel(f"[bright_red]{_timestamp()} 🚨[ERROR] {message}[/bright_red]"))
    else:
        _console.print(f"[bright_red]{_timestamp()} 🚨[ERROR] {message}[/bright_red]")


def ask(message: str) -> str:
    if style == "panel":
        _console.print(Panel(f"[bright_blue]{_timestamp()} 📋[INPUT] {message}[/bright_blue]"))
    else:
        _console.print(f"[bright_blue]{_timestamp()} 📋[INPUT] {message}[/bright_blue]")
    return input()


