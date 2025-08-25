from contextlib import suppress
from netmiko import ConnectHandler
from netmiko.base_connection import BaseConnection 
from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException
from prompt_utils import get_prompt, ensure_enable_mode, EnableModeError
from kero_logging import get_logger
# connect_device.py
# 役割:
# - Netmiko接続の確立（connect_to_device）
# - 失敗/例外時の安全な切断（safe_disconnect）
# このモジュールは「接続ライフサイクル（open/close）」を司る。

_log = get_logger()


def safe_disconnect(connection: BaseConnection | None) -> None:
    """クリーンアップ中の例外で元例外を潰さないために安全に切断する"""
    if connection is None:
        return
    # disconnectの例外は黙って無視する。
    with suppress(Exception): 
        connection.disconnect()


def connect_to_device(device: dict, hostname:str, require_enable: bool = True) -> tuple[BaseConnection, str, str]:
    """
    SSH セッションを確立し、(必要なら) 特権モード (#) に昇格させてから
    Netmiko 接続・現在のプロンプト・ホスト名を返す関数。

    仕様 / 振る舞い
    ---------------
    - require_enable=True のとき:
        - ensure_enable_mode() で enable (#) を保証
        - enable 成功後に set_base_prompt() を 1 回だけ実行
        - get_prompt() で (prompt, hostname) を取得して返却
    - require_enable=False のとき:
        - enable は実施しない（ユーザーモードのまま）
        - set_base_prompt() は実行（ベースプロンプトは確定）

    Parameters
    ----------
    device : dict
        ConnectHandler(**device) に渡すパラメータ辞書（device_type, ip, username, password, secret 等）
    hostname : str
        ログ / エラーメッセージ用の識別子（IP または inventory の hostname）
    require_enable : bool, optional
        True の場合は接続直後に enable を保証する（デフォルト True）

    Returns
    -------
    tuple[BaseConnection, str, str]
        - connection : Netmiko 接続（呼び出し側で必ず disconnect() すること）
        - prompt     : 取得時点の完全なプロンプト文字列（例: "R1#"）
        - hostname   : プロンプトから抽出したホスト名（例: "R1"）

    Raises
    ------
    ConnectionError
        - タイムアウト（NetMikoTimeoutException のラップ）
        - 認証失敗（NetMikoAuthenticationException のラップ）
        - enable 失敗（EnableModeError のラップ）
        - その他の例外の包括ラップ

    Notes
    -----
    - 失敗時は内部で安全にセッションを切断してから ConnectionError を送出する🐸
    - 画面への出力（print_*）は呼び出し側で行うこと
    """
    
    connection: BaseConnection | None = None  # 例外時の安全なdisconnect用に先行定義

    try:   
        connection = ConnectHandler(**device)

        if require_enable:
            try:
                ensure_enable_mode(connection)
            except EnableModeError as e:
                _log.exception(f"[ERROR]: [{hostname}] Enableモード移行に失敗")
                safe_disconnect(connection)
                raise ConnectionError(f"[{hostname}] Enableモードに移行できなかったケロ🐸 Secretが間違ってないケロ？ {e}") from e
        
        # enable成功後にbase promptを一度だけ取得。
        connection.set_base_prompt()
        prompt, hostname = get_prompt(connection)

        return connection, prompt, hostname

    except NetMikoTimeoutException as e:
        _log.exception(f"[ERROR]: [{hostname}] 接続タイムアウト")
        safe_disconnect(connection)
        raise ConnectionError(f"[{hostname}] タイムアウトしたケロ🐸 接続先がオフラインかも") from e
    
    except NetMikoAuthenticationException as e:
        _log.exception(f"[ERROR]: [{hostname}] 認証失敗")
        safe_disconnect(connection)
        raise ConnectionError(f"[{hostname}] 認証に失敗したケロ🐸 ユーザー名とパスワードを確認してケロ") from e

    except Exception as e:
        _log.exception(f"[ERROR]: [{hostname}] 予期しない例外 (connect_to_device)")
        # ConnectHandler失敗直後など、connectionが無い可能性がある
        safe_disconnect(connection)
        raise ConnectionError(f"[{hostname}]に接続できないケロ。🐸 詳細: \n {e}") from e


def connect_to_device_for_console(device: dict, hostname: str, require_enable: bool = True) -> tuple[BaseConnection, str, str]:
    """
    コンソール（serial）向けの Netmiko 接続確立関数。
    - ConnectHandler(**device) で接続（serial_settings を含む dict）
    - require_enable=True のとき enable(#) を保証
    - base_prompt を確定し、(prompt, hostname) を返却

    Returns
    -------
    (connection, prompt, hostname_from_prompt)

    Raises
    ------
    ConnectionError : タイムアウト / 認証失敗 / enable 失敗 / その他一般例外
    """
    # : TODO Console特有のError処理が必要になる。
    connection: BaseConnection | None = None

    device = dict(device)

    # シリアルでもAPIは同じ。host/ip チェックは device 側で満たしておくこと（build_deviceで対応済）
    try:
        connection = ConnectHandler(**device)

        if require_enable:
            try:
                ensure_enable_mode(connection)
            except EnableModeError as e:
                _log.exception(f"[ERROR]: [{hostname}] Enableモード移行に失敗 (console)")
                safe_disconnect(connection)
                raise ConnectionError(f"[{hostname}] Enableモードに移行できなかったケロ🐸 Secretが間違ってないケロ？ {e}") from e

        # enable成功後にbase promptを一度だけ取得。
        connection.set_base_prompt()
        prompt, hostname = get_prompt(connection)

        return connection, prompt, hostname
    
    except NetMikoTimeoutException as e:
        _log.exception(f"[ERROR]: [{hostname}] 接続タイムアウト (console)")
        safe_disconnect(connection)
        raise ConnectionError(f"[{hostname}] タイムアウトしたケロ🐸 接続先がオフラインかも") from e
    
    except NetMikoAuthenticationException as e:
        _log.exception(f"[ERROR]: [{hostname}] 認証失敗 (console)")
        safe_disconnect(connection)
        raise ConnectionError(f"[{hostname}] 認証に失敗したケロ🐸 ユーザー名とパスワードを確認してケロ") from e

    except Exception as e:
        # ConnectHandler失敗直後など、connectionが無い可能性がある
        _log.exception(f"[ERROR]: [{hostname}] 予期しない例外 (connect_to_device_for_console)")
        safe_disconnect(connection)
        raise ConnectionError(f"[{hostname}]に接続できないケロ。🐸 詳細: \n {e}") from e