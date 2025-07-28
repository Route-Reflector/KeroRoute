from netmiko import ConnectHandler
from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException
from utils import ensure_enable_mode


def connect_to_device(device: dict, hostname:str):
    """
    SSH セッションを確立して Netmiko の接続オブジェクトを返す。

    Notes
    -----
    - `device` は Netmiko の `ConnectHandler` が要求するキー (`device_type`, `ip`, `username` …) を
      そのまま持つ辞書であることを前提とする。
    - 接続エラーは Netmiko の例外を捕捉して `ConnectionError` にラップし直すので、呼び出し側は
      `ConnectionError` だけを意識すればよい。

    Parameters
    ----------
    device : dict
        接続パラメータ。`inventory.yaml` あるいは CLI 引数から構築したもの。
    hostname_for_log : str
        エラーメッセージやログ用ファイル名に使う “識別子”。  
        通常は IP アドレスか inventory の `hostname`。

    Returns
    -------
    BaseConnection
        Netmiko の接続オブジェクト。成功すれば必ず `disconnect()` でクローズすること。

    Raises
    ------
    ConnectionError
        - タイムアウト (`NetMikoTimeoutException`)
        - 認証失敗 (`NetMikoAuthenticationException`)
        - それ以外の例外
    """
    # TODO: 将来的にはdevice_typeでCisco以外の他機種にも対応。
    try:   
        connection = ConnectHandler(**device)
        try: 
            ensure_enable_mode(connection)
            return connection
        except ValueError as e:
            connection.disconnect()
            raise ConnectionError(f"[{hostname}] Enableモードに移行できなかったケロ🐸 Secretが間違ってないケロ？ {e}")
    except NetMikoTimeoutException:
        raise ConnectionError(f"[{hostname}] タイムアウトしたケロ🐸 接続先がオフラインかも")
    except NetMikoAuthenticationException:
        raise ConnectionError(f"[{hostname}] 認証に失敗したケロ🐸 ユーザー名とパスワードを確認してケロ")
    except Exception as e:
        raise ConnectionError(f"[{hostname}]に接続できないケロ。🐸 詳細: \n {e}")