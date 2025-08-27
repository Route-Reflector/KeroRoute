from message import print_error


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

    device = {
        "device_type": args.device_type,
        "ip": args.ip,
        "username": args.username,
        "password": args.password,
        "secret": args.secret or args.password,
        "port": args.port,
        "timeout": args.timeout
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
    
    node_info = inventory_data["all"]["hosts"][args.host]
        
    device = {
        "device_type": node_info["device_type"],
        "ip": node_info["ip"],
        "username": node_info["username"],
        "password": node_info["password"],
        "secret": node_info["secret"] or node_info["password"],
        "port": node_info["port"],
        "timeout": node_info["timeout"] 
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
    group_info = inventory_data["all"]["groups"][f"{args.group}"]["hosts"]
        
    device_list = []
    hostname_list = []

    for node in group_info:
        node_info = inventory_data["all"]["hosts"][f"{node}"]
        device = {
            "device_type": node_info["device_type"],
            "ip": node_info["ip"],
            "username": node_info["username"],
            "password": node_info["password"],
            "secret": node_info["secret"] or node_info["password"],
            "port": node_info["port"],
            "timeout": node_info["timeout"] 
            } 
        hostname = node_info["hostname"]
        
        device_list.append(device)
        hostname_list.append(hostname)
    
    return device_list, hostname_list


def build_device_and_hostname(args, inventory_data=None):
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
    if args.ip:
        return _build_device_from_ip(args)
    elif args.host:
        return _build_device_from_host(args, inventory_data)
    elif args.group:
        return _build_device_from_group(args, inventory_data)


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

    baudrate: int = args.baudrate or 9600
    secret: str = getattr(args, "secret", None) or args.password or ""

    device = {
        "device_type": device_type, 
        "host": host_for_netmiko, # シリアルでも必須
        "serial_settings": {
            "port": serial_port,
            "baudrate": baudrate
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

    node_info = inventory_data.get("all", {}).get("hosts", {}).get(f"{args.host}", {})
    if not node_info:
        msg = f"inventoryにホスト '{args.host}' が見つからないケロ🐸"
        print_error(msg)
        raise KeyError(msg)    

    base_device_type = args.device_type or node_info.get("device_type") # --device_typeがあれば上書き。
    device_type = _ensure_serial_device_type(base_device_type)
    
    # Netmiko の必須項目: host or ip
    # inventory の hostname が空なら --host 文字列で埋めておく
    host_for_netmiko = node_info.get("hostname") or args.host

    baudrate: int = args.baudrate if args.baudrate is not None else int(node_info.get("baudrate", 9600))
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


def build_device_and_hostname_for_console(args, inventory_data=None, serial_port=None):
    if args.host:
        return _build_device_for_console_from_host(args, inventory_data, serial_port)
    elif args.group:
        raise NotImplementedError
        return _build_device_for_console_from_group(args, inventory_data, serial_port)
    else:    
        return _build_device_for_console(args, serial_port)