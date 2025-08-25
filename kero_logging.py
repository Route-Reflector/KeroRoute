from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "kero"

def init_logging(log_dir: str | Path = "logs/keroroute", level: str = "INFO", filename: str = "keroroute.log",
    max_bytes: int = 5 * 1024 * 1024, backup_count: int = 3) -> logging.Logger:
    """ファイルにだけ出す最小ロガー。何度呼んでも安全（多重初期化しない）。"""
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger  # すでに初期化済み

    # わかりやすい名前に変更
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    logger.propagate = False  # ルートへ伝播させて二重出力になるのを防止

    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir_path / filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(module)s - %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # ライブラリの騒がしいログは抑える（必要に応じて調整）
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("netmiko").setLevel(logging.INFO)

    # warnings を拾う（DeprecationWarningなど）
    logging.captureWarnings(True)

    return logger

def get_logger() -> logging.Logger:
    """どこからでも同じロガーを取得."""
    return logging.getLogger(_LOGGER_NAME)

