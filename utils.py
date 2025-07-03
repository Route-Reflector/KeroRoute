import re
import ipaddress
from ruamel.yaml import YAML
from pathlib import Path

from rich.box import ROUNDED, SQUARE, DOUBLE


BOX_MAP = {
    "ROUNDED": ROUNDED,
    "SQUARE": SQUARE,
    "DOUBLE": DOUBLE
}


def sanitize_filename_for_log(text: str) -> str:
    """
    ファイル名に使用できない文字を安全な文字に変換する。
    禁止文字: \\ / : * ? " < > | -> "_" アンダースコア
    スペース: " " -> "-" ハイフン
    """

    text = text.replace(" ", "-")
    return re.sub(r'[\\/:*?"<>|]', '_', text).strip()


def is_valid_ip(ip: str) -> bool:
    """IP アドレスが正しい形式か確認する。"""
    """将来的に IPv4アドレス形式かを判定する（今後--ip用などに）"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


_sys_config_cache = None  # 一度だけ読み込むようにキャッシュ

def load_sys_config():
    global _sys_config_cache
    if _sys_config_cache:
        return _sys_config_cache

    config_path = Path("sys_config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("sys_config.yaml が見つからないケロ🐸")

    yaml = YAML()
    with config_path.open("r") as f:
        _sys_config_cache = yaml.load(f)

    return _sys_config_cache


def get_table_theme():

    sys_config_data = load_sys_config()

    return {
    "title_style":  sys_config_data["theme"]["table"]["title_style"],
    "header_style": sys_config_data["theme"]["table"]["header_style"],
    "border_style": sys_config_data["theme"]["table"]["border_style"],
    "box": BOX_MAP.get(sys_config_data["theme"]["table"]["box"])
    }


def get_panel_theme():

    sys_config_data = load_sys_config()

    return {
    "border_style": sys_config_data["theme"]["panel"]["border_style"],
    "style":  sys_config_data["theme"]["panel"]["style"],
    "title_align": sys_config_data["theme"]["panel"]["title_align"],
    "expand": sys_config_data["theme"]["panel"]["expand"]
    }