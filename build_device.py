from load_and_validate_yaml import get_validated_inventory_data
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


def _build_device_and_hostname(args, inventory_data=None):
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


def _build_device_for_console(args, serial_port):
    device = {
        "device_type": args.device_type or "cisco_ios_serial",
        "serial_settings": {
            "port": serial_port,
            "baudrate": args.baudrate
        },
        "username": args.username,     # ログイン要求があれば
        "password": args.password      # 同上
    }

    hostname = ""

    return device, hostname


def _build_device_for_console_from_host(args, inventory_data, serial_port):
    # deviceについては stopbits / parity / bytesize / xonxoff / rtscts / timeout などの拡張が想定される。

    node_info = inventory_data.get("all", {}).get("hosts", {}).get(f"{args.host}", {})
    if not node_info:
        msg = f"inventoryにホスト '{args.host}' が見つからないケロ🐸"
        print_error(msg)
        raise KeyError(msg)    

    device = {
        "device_type": args.device_type or node_info.get("device_type", "cisco_ios_serial"),
        "serial_settings": {
            "port": serial_port,
            "baudrate": int(node_info.get("baudrate", "9600"))
        },
        "username": args.username or node_info.get("username", ""),     # ログイン要求があれば
        "password": args.password or node_info.get("password", "")     # 同上
    }

    hostname = node_info.get("hostname", "")

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