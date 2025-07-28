import re
from netmiko import BaseConnection
import time
from message import print_error


def get_prompt(connection):
    """
    デバイスのプロンプトを取得し、末尾の記号を取り除いたホスト名を返す。

    Args:
        connection (BaseConnection): Netmikoの接続オブジェクト

    Returns:
        tuple[str, str]: プロンプト（例: "R1#"）とホスト名（例: "R1"）
    """
    prompt = connection.find_prompt()
    hostname = re.sub(r'[#>]+$', '', prompt)
    
    return prompt, hostname


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