import argparse
from datetime import datetime
from pathlib import Path
from netmiko import ConnectHandler
from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException
import cmd2
from ruamel.yaml import YAML
from message import print_info, print_success, print_warning, print_error
from utils import sanitize_filename_for_log, load_sys_config
from concurrent.futures import ThreadPoolExecutor, as_completed
import re


#######################
###  CONST_SECTION  ### 
#######################
DEFAULT_MAX_WORKERS = 20 # 並列スレッド上限。(sys_config.yamlに設定が無い場合に参照。)


######################
###  HELP_SECTION  ### 
######################
ip_help = "対象デバイスのIPアドレスを指定します。"
host_help = "inventory.yamlに定義されたホスト名を指定します。"
group_help = "inventory.yamlに定義されたグループ名を指定します。グループ内の全ホストにコマンドを実行します。"

command_help = "1つのコマンドを直接指定して実行します。"
command_list_help = "コマンドリスト名（commands-lists.yamlに定義）を指定して実行します。" \
                    "device_typeはホストから自動で選択されます。"

username_help = "SSH接続に使用するユーザー名を指定します。省略時はinventory.yamlの値を使用します。"
password_help = "SSH接続に使用するパスワードを指定します。省略時はinventory.yamlの値を使用します。"
device_type_help = "Netmikoにおけるデバイスタイプを指定します（例: cisco_ios）。省略時は 'cisco_ios' です。"
port_help = "SSH接続に使用するポート番号を指定します（デフォルト: 22）"
timeout_help = "SSH接続のタイムアウト秒数を指定します（デフォルト: 10秒）"
log_help = ("実行結果をログファイルとして保存します。\n"
           "保存先: logs/execute/\n"
           "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]\n"
           "example: 20250504-235734_R0_show-ip-int-brief.log")
memo_help = ("ログファイル名に付加する任意のメモ（文字列）を指定します。\n"
             "保存先: logs/execute/\n"
             "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]_[memo]\n"
             "example 20250506-125600_R0_show-ip-int-brief_memo.log")
workers_help = ("並列実行するワーカースレッド数を指定します。\n"
                "指定しない場合は sys_config.yaml の executor.default_workers を参照します。\n"
                "そこにも設定が無いときは、グループ台数と 規定上限(DEFAULT_MAX_WORKERS) の小さい方が自動で採用されます。")



######################
### PARSER_SECTION ###
######################
netmiko_execute_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
# "-h" はhelpと競合するから使えない。
netmiko_execute_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_execute_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_execute_parser.add_argument("-d", "--device_type", type=str, default="cisco_ios", help=device_type_help)
netmiko_execute_parser.add_argument("-P", "--port", type=int, default=22, help=port_help)
netmiko_execute_parser.add_argument("-t", "--timeout", type=int, default=10, help=timeout_help)
netmiko_execute_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_execute_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)
netmiko_execute_parser.add_argument("-w", "--workers", type=int, default=None, metavar="N", help=workers_help)

# mutually exclusive
target_node = netmiko_execute_parser.add_mutually_exclusive_group(required=True)
target_node.add_argument("-i", "--ip", type=str, nargs="?", default=None, help=ip_help)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help)

target_command = netmiko_execute_parser.add_mutually_exclusive_group(required=True)
target_command.add_argument("-c", "--command", type=str, default="", help=command_help)
target_command.add_argument("-L", "--commands-list", type=str, default="", help=command_list_help)


def validate_commands_list(args, device):
    """
    commands-lists.yaml に基づいて、指定されたコマンドリストの存在を検証する。

    Args:
        args: argparse.Namespace - コマンドライン引数
        device: dict - 接続対象のデバイス情報（device_type含む）

    Returns:
        commands_lists_data

    Raises:
        FileNotFoundError: commands-lists.yaml が存在しない場合
        ValueError: device_type または commands_list が未定義の場合
    """

    # ✅ commands-listが指定されている場合は先に存在チェック

    if not args.commands_list:
        msg = "-L or --commands_list が指定されていないケロ🐸"
        print_error(msg)
        raise ValueError(msg)

    if args.commands_list:
        commands_lists_path = Path("commands-lists.yaml")
        if not commands_lists_path.exists():
            msg = "commands-lists.yaml が見つからないケロ🐸"
            print_error(msg)
            raise FileNotFoundError(msg)

        yaml = YAML()
        with commands_lists_path.open("r") as f:
            commands_lists_data = yaml.load(f)

        device_type = device["device_type"]

        if device_type not in commands_lists_data["commands_lists"]:
            msg = f"デバイスタイプ '{device_type}' はcommands-lists.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)

        if args.commands_list not in commands_lists_data["commands_lists"][device_type]:
            msg = f"コマンドリスト '{args.commands_list}' はcommands-lists.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)
    
    return commands_lists_data


def _connect_to_device(device: dict, hostname_for_log:str):
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
        return connection
    except NetMikoTimeoutException:
        raise ConnectionError(f"[{hostname_for_log}] タイムアウトしたケロ🐸 接続先がオフラインかも")
    except NetMikoAuthenticationException:
        raise ConnectionError(f"[{hostname_for_log}] 認証に失敗したケロ🐸 ユーザー名とパスワードを確認してケロ")
    except Exception as e:
        raise ConnectionError(f"[{hostname_for_log}]に接続できないケロ。🐸 詳細: \n {e}")

def _get_prompt(connection):
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


def _execute_command(connection, prompt, command):
    """
    単一コマンドをNetmikoで実行し、プロンプト付きで出力を整形して返す。

    Args:
        connection: Netmikoの接続オブジェクト
        prompt (str): コマンド実行時のプロンプト
        command (str): 実行するコマンド

    Returns:
        str: 実行結果（プロンプト＋コマンド＋出力）
    """
    prompt = connection.find_prompt()
    output = connection.send_command(command)
    full_output = f"{prompt} {command}\n{output}\n"

    return full_output

def _execute_commands_list(connection, prompt, hostname_for_log, args, device):
    """
    commands-lists.yaml で定義された「コマンドリスト」を順次実行する。

    Parameters
    ----------
    connection : BaseConnection
        `_connect_to_device()` で取得した Netmiko 接続。
    prompt : str
        デバイスのプロンプト文字列（例: ``"R1#"``)
    hostname_for_log : str
        メッセージ表示や例外ラップ用の識別子。
    args : argparse.Namespace
        CLI 引数オブジェクト。`args.commands_list` を使用。
    device : dict
        対象デバイス辞書。ここでは主に `device['device_type']` を参照。

    Returns
    -------
    str
        各コマンド実行結果を改行で連結したテキスト。

    Raises
    ------
    FileNotFoundError
        `commands-lists.yaml` が存在しない場合
    ValueError
        device_type 不一致や commands_list 未定義など、ユーザ入力に起因する不整合
    KeyError
        YAML 構造が想定外だった場合
    """

    try:
        commands_lists_data = validate_commands_list(args, device)
        exec_commands = commands_lists_data["commands_lists"][device["device_type"]][f"{args.commands_list}"]["commands_list"]
    except Exception as e:
        msg = f"[{hostname_for_log}] commands-lists.yamlの構造がおかしいケロ🐸 詳細: {e}"
        print_error(msg)
        raise KeyError(msg)

    full_output_list = []

    for command in exec_commands:
        output = connection.send_command(command)
        full_output = f"{prompt} {command}\n{output}\n"
        full_output_list.append(full_output)
    
    return "\n".join(full_output_list)


def _execute_commands(connection, prompt, hostname, args, poutput, device):
    """
    指定されたコマンド（単発 or コマンドリスト）を実行し、出力を返すラッパー関数。

    Args:
        connection: Netmikoの接続オブジェクト
        prompt (str): デバイスのプロンプト（例: "R1#"）
        hostname (str): 子関数 `_execute_commands_list` に渡すための識別子。本関数内では直接使用しない。
        args: コマンドライン引数（args.command または args.commands_list を含む）
        poutput: cmd2 の出力関数（エラーメッセージ表示に使用）
        device (dict): 対象デバイスの情報（device_typeなどを含む）

    Returns:
        str: 実行結果（複数コマンドの場合は結合済み出力）

    Raises:
        ValueError: args.command または args.commands_list のいずれも指定されていない場合
    """
    if args.command:
        return _execute_command(connection, prompt, args.command)
    elif args.commands_list:
        return _execute_commands_list(connection, prompt, hostname, args, poutput, device)
    else:
        raise ValueError("command または commands_list のいずれかが必要ケロ🐸")



def _save_log(result_output_string: str, hostname: str, args, mode: str = "execute") -> None:
    """
    実行結果を日時付きファイルに保存するユーティリティ。

    ファイル名フォーマット
    --------------------
    ``{YYYYmmdd-HHMMSS}_{hostname}_{command|list}[_{memo}].log``

    Parameters
    ----------
    result_output_string : str
        コマンド実行結果全体（単発でも複数でも OK）。
    hostname : str
        ログファイル名に含めるホスト名。
    args : argparse.Namespace
        CLI 引数。`--log`, `--memo`, `--command`, `--commands-list` を参照。
    mode: str, optional
         ログ保存モード（"execute", "console", など）。デフォルトは "execute"。
    
    Returns
    -------
    None

    Raises
    ------
    ValueError
        - `--memo` だけ指定された場合
        - `--command` / `--commands-list` どちらも無い場合
    IOError
        ファイル書き込み失敗（上位で捕捉してもよい）
    """
    if args.memo and not args.log:
        msg = "--memo は --log が指定されているときだけ有効ケロ🐸"
        print_warning(msg)
        raise ValueError(msg)
    
    if args.log:
        print_info("💾ログ保存モードONケロ🐸🔛")
        date_str = datetime.now().strftime("%Y%m%d")
        log_dir = Path("logs") / mode / date_str
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if args.command:
            sanitized_command = sanitize_filename_for_log(args.command)
        elif args.commands_list:
            sanitized_command = sanitize_filename_for_log(args.commands_list)
        else:
            raise ValueError("args.command または args.commands_list のどちらかが必須ケロ！🐸")

        if args.memo == "":
            file_name = f"{timestamp}_{hostname}_{sanitized_command}.log"
        else:
            sanitized_memo = sanitize_filename_for_log(args.memo)
            file_name = f"{timestamp}_{hostname}_{sanitized_command}_{sanitized_memo}.log"
        
        log_path = log_dir / file_name

        with open(log_path, "w") as log_file:
            log_file.write(result_output_string)
            print_success(f"💾ログ保存完了ケロ🐸⏩⏩⏩ {log_path}")



def _handle_execution(device: dict, args, poutput, hostname_for_log):
    """
    デバイス接続〜コマンド実行〜ログ保存までをまとめて処理するラッパー関数。

    Args:
        device (dict): 接続情報を含むデバイス辞書
        args: コマンドライン引数
        poutput: cmd2 の出力関数
        hostname_for_log (str): ログファイル名などに使うホスト識別子
    """

    # ✅ 1. commands-list の存在チェック（必要なら）
    try:
        if args.commands_list:
            validate_commands_list(args, device)
    except (FileNotFoundError, ValueError):
        return

    # ✅ 2. 接続とプロンプト取得
    try:
        connection = _connect_to_device(device, hostname_for_log)
        print_success(f"NODE: {hostname_for_log} 🔗接続成功ケロ🐸")
        prompt, hostname = _get_prompt(connection)
    except ConnectionError as e:
        print_error(str(e))
        return

    # ✅ 3. コマンド実行（単発 or リスト）
    try:
        result_output_string = _execute_commands(connection, prompt, hostname, args, poutput, device)
    except (KeyError, ValueError) as e:
        print_error(str(e))
        connection.disconnect()
        return

    # ✅ 4. 接続終了
    connection.disconnect()

    # ✅ 5. ログ保存（--log指定時のみ）
    if args.log:
        _save_log(result_output_string, hostname, args, poutput)

    # ✅ 6. 結果表示
    print_info(f"NODE: {hostname_for_log} 📄OUTPUTケロ🐸")
    poutput(result_output_string)
    print_success(f"NODE: {hostname_for_log} 🔚実行完了ケロ🐸")


def _load_and_validate_inventory(host=None, group=None):
    """
    inventory.yaml を読み込み、指定されたホストまたはグループの存在を検証する。

    Parameters
    ----------
    host : str, optional
        inventory.yaml 内のホスト名。指定されている場合は存在を検証する。
    group : str, optional
        inventory.yaml 内のグループ名。指定されている場合は存在を検証する。

    Returns
    -------
    dict
        パース済みの inventory データ。

    Raises
    ------
    FileNotFoundError
        inventory.yaml が見つからない場合。
    ValueError
        指定された host または group が inventory.yaml に存在しない場合。
    """

    inventory_path = Path("inventory.yaml")
    if not inventory_path.exists():
        raise FileNotFoundError("inventory.yamlが存在しないケロ🐸")

    yaml = YAML()
    with open(inventory_path, "r") as inventory:
        inventory_data = yaml.load(inventory)

    if host and host not in inventory_data["all"]["hosts"]:
            msg = f"ホスト '{host}' はinventory.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)

    elif group and group not in inventory_data["all"]["groups"]:
            msg = f"グループ '{group}' はinventory.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)
    
    return inventory_data
    

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
        "port": args.port,
        "timeout": args.timeout
        }

    hostname_for_log = args.ip
    return device, hostname_for_log


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
        "port": node_info["port"],
        "timeout": node_info["timeout"] 
        }

    hostname_for_log = node_info["hostname"]
    return device, hostname_for_log 


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
    hostname_for_log_list = []

    for node in group_info:
        node_info = inventory_data["all"]["hosts"][f"{node}"]
        device = {
            "device_type": node_info["device_type"],
            "ip": node_info["ip"],
            "username": node_info["username"],
            "password": node_info["password"],
            "port": node_info["port"],
            "timeout": node_info["timeout"] 
            } 
        hostname_for_log = node_info["hostname"]
        
        device_list.append(device)
        hostname_for_log_list.append(hostname_for_log)
    
    return device_list, hostname_for_log_list


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


def _default_workers(group_size: int, args) -> int:
    """
    並列実行に使うワーカースレッド数（max_workers）を決定する。

    決定ロジックの優先順位：
    1. CLI 引数 `--workers` が指定されていればその値を使う（1以上の整数のみ有効）
    2. 指定がなければ `sys_config.yaml` の `executor.default_workers` を参照
    3. どちらにもなければ `DEFAULT_MAX_WORKERS`（定数）を使用

    ただし、最終的には `group_size`（ホスト台数）と `DEFAULT_MAX_WORKERS` の両方を超えないように調整する。

    Parameters
    ----------
    group_size : int
        グループに含まれるホストの台数（並列実行する対象数）
    args : argparse.Namespace
        コマンドライン引数オブジェクト。`args.workers` を参照

    Returns
    -------
    int
        実際に ThreadPoolExecutor に渡す `max_workers` の値

    Raises
    ------
    ValueError
        - `--workers` に無効な値（0以下や非整数）が指定された場合
        - `sys_config.yaml` に不正な型や値が書かれていた場合
    """
    workers = args.workers

    if workers or workers == 0: # workers が None なら False、0 だけ特別に True 扱い
        if type(workers) != int:
                msg = "--workersは整数である必要があるケロ🐸。"
                raise ValueError(msg)

        if workers <= 0:
            msg = "--workersには1以上の整数を指定してくださいケロ🐸"
            raise ValueError(msg)

    else:
        system_config = load_sys_config()
        workers = system_config["executor"].get("default_workers", DEFAULT_MAX_WORKERS)

        if type(workers) != int:
                msg = "sys_config.yamlのexecutor.default_workerは整数である必要があるケロ🐸。"
                raise ValueError(msg)
        
        if workers <= 0:
            msg = "executor.default_workersには1以上の整数を指定してくださいケロ🐸"
            raise ValueError(msg)


    workers = min(workers, group_size, DEFAULT_MAX_WORKERS)
    return workers


@cmd2.with_argparser(netmiko_execute_parser)
def do_execute(self, args):
    """
    `execute` サブコマンドのエントリポイント。

    ルーティング
    ------------
    1. `--ip` 指定 → 単一デバイス  
    2. `--host`    → inventory から 1 台  
    3. `--group`   → inventory グループ内の複数台（※並列化は今後）

    Notes
    -----
    - 実処理は `_handle_execution()` に委譲。
    - `cmd2` では ``self.poutput`` が標準出力をラップしているため、
      すべての内部関数にこれを渡してカラー表示や装飾を統一している。
    """

    if args.ip:
        device, hostname_for_log = _build_device_and_hostname(args)
        _handle_execution(device, args, self.poutput, hostname_for_log)
        return

    if args.host or args.group: 
        try:
            inventory_data = _load_and_validate_inventory(host=args.host, group=args.group)
        
        except (FileNotFoundError, ValueError) as e:
            print_error(self.poutput, str(e))
            return
        
    
    if args.host:
        device, hostname_for_log = _build_device_and_hostname(args, inventory_data)
        _handle_execution(device, args, self.poutput, hostname_for_log)
        return

    elif args.group:
        device_list, hostname_for_log_list = _build_device_and_hostname(args, inventory_data)

        max_workers = _default_workers(len(device_list), args)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:

            futures = []
            for device, hostname_for_log in zip(device_list, hostname_for_log_list):
                future = pool.submit(_handle_execution, device, args, self.poutput, hostname_for_log)
                futures.append(future)

            for future in as_completed(futures):
                future.result()


