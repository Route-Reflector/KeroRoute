import ipaddress
from netmiko import BaseConnection
import time
from message import print_error
from rich.box import ROUNDED, SQUARE, DOUBLE


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



# TODO: 将来的にはtheme_utils.pyに切り出す予定

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


def wait_for_prompt_returned(connection, sleep_time=0.1, max_retry=3):
    """
    端末プロンプトが戻るのを待機して確認するユーティリティ。

    Parameters
    ----------
    connection : Netmiko BaseConnection
        既に確立済みの Netmiko 接続オブジェクト。
    sleep_time : float, optional
        再試行のインターバル秒数。デフォルト 0.1 秒（SSH 向け）。
    max_retry : int, optional
        プロンプト確認を試みる回数。デフォルト 3 回。

    Raises
    ------
    ValueError
        max_retry 回試してもプロンプトが検出できなかった場合。
    """
    from message import print_error, print_info

    for attempt in range(1, max_retry + 1):
        try:
            time.sleep(sleep_time)              # 応答の余韻待ち
            _ = connection.find_prompt()        # 戻り値は不要なので捨てる
            return                              # ✓ 成功 → そのまま抜ける
        except Exception as e:
            if attempt < max_retry:
                print_info(
                    f"⌛ プロンプト待機再試行 {attempt}/{max_retry} ケロ🐸 "
                    f"({e})"
                )
            else:
                msg = (
                    "プロンプトが戻らなかったケロ🐸 "
                    f"({max_retry} 回試してもダメ)"
                )
                print_error(msg)
                # 必要なら元例外を連結しても良い
                raise ValueError(msg) from e


def ensure_enable_mode(connection: BaseConnection):    
    """
    connection が必ず enable (#) モードになるよう保証する。
    失敗したら EnableModeError を投げる。
    """
    if not connection.check_enable_mode():
        try: 
            connection.enable()
        except Exception as e:
            msg = f"Enableモードに移行できなかったケロ🐸 {e}"
            print_error(msg)
            raise ValueError(msg)
    
    connection.set_base_prompt()