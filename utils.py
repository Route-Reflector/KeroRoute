import ipaddress
from rich.box import ROUNDED, SQUARE, DOUBLE
from load_and_validate_yaml import load_sys_config

BOX_MAP = {
    "ROUNDED": ROUNDED,
    "SQUARE": SQUARE,
    "DOUBLE": DOUBLE
}


def is_valid_ip(ip: str) -> bool:
    """IP アドレスが正しい形式か確認する。"""
    """将来的に IPv4アドレス形式かを判定する（今後--ip用などに）"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


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


