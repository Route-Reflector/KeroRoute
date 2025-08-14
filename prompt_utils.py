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
        tuple[str, str]: プロンプト（例: "R1(config-if)#"）とホスト名（例: "R1"）
    """
    prompt = connection.find_prompt()
    hostname = re.split(r'[\(#>]', prompt, 1)[0]
    
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

class EnableModeError(ValueError):
    """特権モード(enable #)への移行に失敗したことを示す例外"""
    # 専用例外クラスを作成する理由:
    # - ensure_enable_mode() 専用のエラー種別を用意することで、
    #   呼び出し側が except EnableModeError: のように個別処理できる
    # - ValueError を継承しているので、汎用的な「値が想定と違う」例外として扱える
    pass


def ensure_enable_mode(connection: BaseConnection) -> None:
    """
    接続オブジェクトを必ず enable (#) モードに昇格させる。
    - check_enable_mode() で現在のモードを確認し、必要なら enable() を実行
    - 最終的に enable モードでなければ EnableModeError を送出
    - メッセージ出力は行わず、呼び出し側で例外処理する設計

    Parameters
    ----------
    connection : BaseConnection
        Netmiko 接続オブジェクト

    Raises
    ------
    EnableModeError
        enable モードに移行できなかった場合
    """
    try: 
        if not connection.check_enable_mode():
            connection.enable()
        if not connection.check_enable_mode():
            raise EnableModeError("Enable Modeに移行できなかったケロ🐸")
    except Exception as e:
            raise EnableModeError(str(e)) from e
        # `from e` の意味:
        # from e を付けると、「元の例外 e（Netmiko内部の例外など）を原因（cause）として保持」
        # スタックトレース上で “During handling of the above exception, another exception occurred:” と因果関係が見える