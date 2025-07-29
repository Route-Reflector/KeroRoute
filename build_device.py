

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