#####################
### CONST_SECTION ###
#####################
DEFAULT_SSH_PORT = 22
DEFAULT_TELNET_PORT = 23
DEFAULT_TIMEOUT_SECONDS = 10
TIMEOUT_MINIMUM_SECONDS = 1
TIMEOUT_MAXIMUM_SECONDS = 600
DEFAULT_BAUDRATE = 9600
ALLOWED_BAUDRATES = {9600, 19200, 38400, 57600, 115200}


def _validate_port(port):
    if port is None:
        return None

    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError(f"portは整数で指定してケロ🐸: {port}")

    if not (1 <= port <= 65535):
        raise ValueError("portは 1-65535 の範囲で指定してケロ🐸")

    return port 


def _validate_timeout(timeout, *, min_sec=TIMEOUT_MINIMUM_SECONDS, max_sec=TIMEOUT_MAXIMUM_SECONDS):
    if timeout is None:
       return None

    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        raise ValueError(f"timeoutは整数で指定してケロ🐸: {timeout}")
    
    if not (min_sec <= timeout <= max_sec):
       raise ValueError(f"timeoutは {min_sec} - {max_sec} の範囲で指定してケロ🐸")

    return timeout

def _validate_baudrate(baudrate):
    if baudrate is None:
        return None
    
    try:
        baudrate = int(baudrate)
    except (TypeError, ValueError):
        raise ValueError(f"baudrateは整数で指定してケロ🐸: {baudrate}")
    
    if baudrate not in ALLOWED_BAUDRATE:
        raise ValueError(f"baudrate は次の中から選んでケロ🐸: {sorted(ALLOWED_BAUDRATES)}")
    return baudrate


def _build_device_from_ip(args):
    """
    --ip オプションが指定されたときに、接続に必要な device 情報とログ用ホスト名を構築する。

    Args:
        args (argparse.Namespace): コマンドライン引数。args.ip などが含まれる。

    Returns:
        tuple[dict, str]: 
            - device: Netmiko 用の接続情報を格納した辞書。
            - hostname_for_log: ログファイル名などに使うホスト識別名（IPアドレス）。
    """
    port = args.port if getattr(args, "port", None) is not None else DEFAULT_SSH_PORT
    timeout = args.timeout if getattr(args, "timeout", None) is not None else DEFAULT_TIMEOUT_SECONDS

    port = _validate_port(port)
    timeout = _validate_timeout(timeout)

    device = {
        "device_type": args.device_type,
        "ip": args.ip,
        "username": args.username,
        "password": args.password,
        "secret": args.secret or args.password,
        "port": port,
        "timeout": timeout
        }

    hostname = args.ip
    return device, hostname


def _build_device_from_host(args, inventory_data):
    """
    --host オプションが指定されたときに、inventory.yaml から接続情報を取得して構築する。

    Args:
        args (argparse.Namespace): コマンドライン引数。args.host が指定されている必要がある。
        inventory_data (dict): inventory.yaml をパースした辞書データ。

    Returns:
        tuple[dict, str]: 
            - device: Netmiko 用の接続情報を格納した辞書。
            - hostname_for_log: ログファイル名などに使うホスト識別名（inventory の hostname）。
    """
    port = args.port if getattr(args, "port", None) is not None else DEFAULT_SSH_PORT
    timeout = args.timeout if getattr(args, "timeout", None) is not None else DEFAULT_TIMEOUT_SECONDS
    
    port = _validate_port(port)
    timeout = _validate_timeout(timeout)

    node_info = inventory_data["all"]["hosts"][args.host]
    
    device = {
        # CLIがあれば優先、なければinventory
        "device_type": args.device_type or node_info["device_type"],
        "ip": node_info["ip"],
        "username": args.username or node_info["username"],
        "password": args.password or node_info["password"],
        # secret は CLI → inventory.secret → inventory.password の順でフォールバック
        "secret": (args.secret or node_info.get("secret") or node_info["password"]),
        "port": port,
        "timeout": timeout,
    }

    hostname = node_info["hostname"]
    return device, hostname 


def _build_device_from_group(args, inventory_data):
    """
    --group オプションが指定されたときに、inventory.yaml 内の全ホスト分の接続情報を構築する。

    Args:
        args (argparse.Namespace): コマンドライン引数。args.group が指定されている必要がある。
        inventory_data (dict): inventory.yaml をパースした辞書データ。

    Returns:
        tuple[list[dict], list[str]]: 
            - device_list: 各ホストの Netmiko 用接続情報のリスト。
            - hostname_for_log_list: 各ホストの hostname（ログ用）のリスト。
    """
    port = args.port if getattr(args, "port", None) is not None else DEFAULT_SSH_PORT
    timeout = args.timeout if getattr(args, "timeout", None) is not None else DEFAULT_TIMEOUT_SECONDS
    
    port = _validate_port(port)
    timeout = _validate_timeout(timeout)
    
    group_info = inventory_data["all"]["groups"][args.group]["hosts"]
        
    device_list = []
    hostname_list = []

    for node in group_info:
        node_info = inventory_data["all"]["hosts"][node]
        device = {
            # CLIがあれば優先、なければinventory
            "device_type": args.device_type or node_info["device_type"],
            "ip": node_info["ip"],
            "username": args.username or node_info["username"],
            "password": args.password or node_info["password"],
            # secret は CLI → inventory.secret → inventory.password の順でフォールバック
            "secret": (args.secret or node_info.get("secret") or node_info["password"]),
            "port": port,
            "timeout": timeout,
        }
        hostname = node_info["hostname"]
        
        device_list.append(device)
        hostname_list.append(hostname)
    
    return device_list, hostname_list


def _ensure_telnet_device_type(device_type: str | None) -> str:
    """
    inventory には 'cisco_ios' などの“素の型”を書いておく前提。
    telnet 用ではここで必ず *_telnet に正規化する。
    """
    if not device_type:
        raise ValueError("'device_type' が指定されていないケロ🐸 'inventory.yaml' または '--device-type' を確認してケロ")
    return device_type if device_type.endswith("_telnet") else f"{device_type}_telnet"


def _build_device_for_telnet_from_ip(args):
    port = args.port if getattr(args, "port", None) is not None else DEFAULT_TELNET_PORT
    timeout = args.timeout if getattr(args, "timeout", None) is not None else DEFAULT_TIMEOUT_SECONDS

    port = _validate_port(port)
    timeout = _validate_timeout(timeout)
    
    device_type = _ensure_telnet_device_type(args.device_type)

    device = {
    "device_type": device_type,
    "ip": args.ip,
    "username": args.username,
    "password": args.password,
    "secret": args.secret or args.password,
    "port": port,
    "timeout": timeout
    }

    hostname = args.ip
    return device, hostname


def _build_device_for_telnet_from_host(args, inventory_data=None):
    port = args.port if getattr(args, "port", None) is not None else DEFAULT_TELNET_PORT
    timeout = args.timeout if getattr(args, "timeout", None) is not None else DEFAULT_TIMEOUT_SECONDS
    
    port = _validate_port(port)
    timeout = _validate_timeout(timeout)

    node_info = inventory_data["all"]["hosts"][args.host]

    base_device_type = args.device_type or node_info["device_type"]
    device_type = _ensure_telnet_device_type(base_device_type)
    
    device = {
        # CLIがあれば優先、なければinventory
        "device_type": device_type,
        "ip": node_info["ip"],
        "username": args.username or node_info["username"],
        "password": args.password or node_info["password"],
        # secret は CLI → inventory.secret → inventory.password の順でフォールバック
        "secret": (args.secret or node_info.get("secret") or node_info["password"]),
        "port": port,
        "timeout": timeout,
    }

    hostname = node_info["hostname"]
    return device, hostname 


def _build_device_for_telnet_from_group(args, inventory_data=None):
    port = args.port if getattr(args, "port", None) is not None else DEFAULT_TELNET_PORT
    timeout = args.timeout if getattr(args, "timeout", None) is not None else DEFAULT_TIMEOUT_SECONDS
    
    port = _validate_port(port)
    timeout = _validate_timeout(timeout)
    
    group_info = inventory_data["all"]["groups"][args.group]["hosts"]
        
    device_list = []
    hostname_list = []

    for node in group_info:
        node_info = inventory_data["all"]["hosts"][node]

        base_device_type = args.device_type or node_info["device_type"]
        device_type = _ensure_telnet_device_type(base_device_type)    

        device = {
            # CLIがあれば優先、なければinventory
            "device_type": device_type,
            "ip": node_info["ip"],
            "username": args.username or node_info["username"],
            "password": args.password or node_info["password"],
            # secret は CLI → inventory.secret → inventory.password の順でフォールバック
            "secret": (args.secret or node_info.get("secret") or node_info["password"]),
            "port": port,
            "timeout": timeout,
        }
        hostname = node_info["hostname"]
        
        device_list.append(device)
        hostname_list.append(hostname)
    
    return device_list, hostname_list


def _ensure_serial_device_type(device_type: str | None) -> str:
    """
    inventory には 'cisco_ios' などの“素の型”を書いておく前提。
    console 用ではここで必ず *_serial に正規化する。
    """
    # device_typeが_serialで終わっていたらそのまま、device_typeが_serial以外だと_serialを付与。
    if not device_type:
        raise ValueError("'device_type' が指定されていないケロ🐸 'inventory.yaml' または '--device-type' を確認してケロ")
    
    return device_type if device_type.endswith("_serial") else f"{device_type}_serial"
    

def _build_device_for_console(args, serial_port):
    """
    --host 未指定パス（手動指定のみ）。host/ip が必須なのでダミーでも host を入れる。
    """
    if serial_port is None:
        raise ValueError("serial_port が None ケロ🐸 '--serial' を確認してケロ")

    device_type = _ensure_serial_device_type(args.device_type)
    # Netmiko の必須項目: host or ip
    host_for_netmiko = args.host or "console-session"

    baudrate: int = args.baudrate if getattr(args, "baudrate", None) is not None else DEFAULT_BAUDRATE
    baudrate = _validate_baudrate(baudrate)
    secret: str = getattr(args, "secret", None) or args.password or ""

    device = {
        "device_type": device_type, 
        "host": host_for_netmiko, # シリアルでも必須
        "serial_settings": {
            "port": serial_port,
            "baudrate": baudrate,
        },
        "username": args.username or "",     # ログイン要求があれば
        "password": args.password or "",      # 同上
        "secret": secret
    }

    # hostname は接続後に base_prompt で上書きされる想定。ここでは仮でOK
    hostname = host_for_netmiko
    return device, hostname


def _build_device_for_console_from_host(args, inventory_data, serial_port):
    """
    --host 指定パス。inventory の device_type は素の型（例: cisco_ios）を想定。
    ここで *_serial に正規化する。username/password は CLI 指定があれば優先。
    deviceについては stopbits / parity / bytesize / xonxoff / rtscts / timeout などの拡張が想定される。
    """
    if serial_port is None:
        raise ValueError("serial_port が None ケロ🐸 '--serial' を確認してケロ")

    node_info = inventory_data.get("all", {}).get("hosts", {}).get(args.host, {})
    if not node_info:
        raise KeyError(f"inventoryにホスト '{args.host}' が見つからないケロ🐸")

    base_device_type = args.device_type or node_info.get("device_type") # --device_typeがあれば上書き。
    device_type = _ensure_serial_device_type(base_device_type)
    
    # Netmiko の必須項目: host or ip
    # inventory の hostname が空なら --host 文字列で埋めておく
    host_for_netmiko = node_info.get("hostname") or args.host

    baudrate: int = args.baudrate if getattr(args, "baudrate", None) is not None else DEFAULT_BAUDRATE
    baudrate = _validate_baudrate(baudrate)
    secret: str = (getattr(args, "secret", None) or node_info.get("secret", "") or args.password or node_info.get("password", "") or "")

    device = {
        "device_type": device_type,
        "host" : host_for_netmiko,
        "serial_settings": {
            "port": serial_port,
            "baudrate": baudrate
        },
        "username": args.username or node_info.get("username", ""),     # ログイン要求があれば
        "password": args.password or node_info.get("password", ""),     # 同上
        "secret": secret
    }

    hostname = host_for_netmiko
    return device, hostname


def _build_device_for_console_from_group():
    # NotImplemented
    raise NotImplementedError


def build_device_and_hostname(args, inventory_data=None, serial_port=None):
    """
    --ip / --host / --group に応じて接続情報を構築するラッパー関数。

    Args:
        args: コマンドライン引数。--ip / --host / --group のいずれかが指定されていること。
        inventory_data: host/group指定時に使用する inventory.yaml のパース結果。

    Returns:
        tuple: 
            - --ip or --host: (dict, str) - 単一のdevice定義とhostname
            - --group: (list[dict], list[str]) - 複数deviceとhostnameのリスト
    """
    if not args.via:
        raise ValueError("viaが無いのは想定して無いケロ🐸")
    
    if args.via == "ssh":
        if args.ip:
            return _build_device_from_ip(args)
        elif args.host:
            return _build_device_from_host(args, inventory_data)
        elif args.group:
            return _build_device_from_group(args, inventory_data)
        
    elif args.via == "telnet":
        if args.ip:
            return _build_device_for_telnet_from_ip(args)
        elif args.host:
            return _build_device_for_telnet_from_host(args, inventory_data)
        elif args.group:
            return _build_device_for_telnet_from_group(args, inventory_data)

    elif args.via == "console":
        if args.host:
            return _build_device_for_console_from_host(args, inventory_data, serial_port)
        elif args.group:
            raise NotImplementedError
            return _build_device_for_console_from_group(args, inventory_data, serial_port)
        else:    
            return _build_device_for_console(args, serial_port)
    
    else:
        raise ValueError(f"未対応の via ケロ🐸: {args.via}")
    
