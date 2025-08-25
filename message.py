from rich.console import Console
from rich.panel import Panel
from datetime import datetime

from kero_logging import get_logger


def get_style() -> str:
    from load_and_validate_yaml import load_sys_config
    return load_sys_config().get("user_interface", {}).get("message_style", "plain")


_console = Console()
_log = get_logger() # main.pyでinit_logging()済みのロガーを取得


def _timestamp() -> str:
    now = datetime.now()
    return f"[{now.strftime('%H:%M:%S')}.{int(now.microsecond / 1000):03d}]"


def print_info(message: str, panel: bool = False):
    show_panel = panel or (style == "panel")
    content = f"[bright_cyan]{_timestamp()} 🪧[INFO] {message}[/bright_cyan]"
    if show_panel:
        _console.print(Panel(content))
    else:
        _console.print(content)
    _log.info(f"[INFO]: {str(message)}") # keroroute.logに同じ内容を出す。


def print_success(message: str):
    if style == "panel":
        _console.print(Panel(f"[bright_green]{_timestamp()} 💯[SUCCESS] {message}[/bright_green]"))
    else:
        _console.print(f"[bright_green]{_timestamp()} 💯[SUCCESS] {message}[/bright_green]")
    _log.info(f"[SUCCESS]: {str(message)}") # keroroute.logに同じ内容を出す。


def print_warning(message: str):
    if style == "panel":
        _console.print(Panel(f"[bright_yellow]{_timestamp()} 🚧[WARNING] {message}[/bright_yellow]"))
    else:
        _console.print(f"[bright_yellow]{_timestamp()} 🚧[WARNING] {message}[/bright_yellow]")
    _log.warning(f"[WARNING]: {str(message)}") # keroroute.logに同じ内容を出す。


def print_error(message: str):
    if style == "panel":
        _console.print(Panel(f"[bright_red]{_timestamp()} 🚨[ERROR] {message}[/bright_red]"))
    else:
        _console.print(f"[bright_red]{_timestamp()} 🚨[ERROR] {message}[/bright_red]")
    _log.error(f"[ERROR]: {str(message)}") # keroroute.logに同じ内容を出す。


def ask(message: str) -> str:
    if style == "panel":
        _console.print(Panel(f"[bright_blue]{_timestamp()} 📋[INPUT] {message}[/bright_blue]"))
    else:
        _console.print(f"[bright_blue]{_timestamp()} 📋[INPUT] {message}[/bright_blue]")
    return input()


style = get_style()
