import argparse
from pathlib import Path
import cmd2
from ruamel.yaml import YAML
from message import print_info, print_success, print_warning, print_error
from executor import _load_and_validate_inventory, _connect_to_device, _get_prompt, _default_workers
from output_logging import _save_log
from build_device import _build_device_and_hostname
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import ensure_enable_mode

######################
###  HELP_SECTION  ### 
######################
ip_help = "対象デバイスのIPアドレスを指定します。"
host_help = "inventory.yamlに定義されたホスト名を指定します。"
group_help = "inventory.yamlに定義されたグループ名を指定します。グループ内の全ホストにコマンドを実行します。"

command_help = "1つのコマンドを直接指定して実行します。"
command_list_help = "コマンドリスト名（config-lists.yamlに定義）を指定して実行します。" \
                    "device_typeはホストから自動で選択されます。"

username_help = "SSH接続に使用するユーザー名を指定します。省略時はinventory.yamlの値を使用します。"
password_help = "SSH接続に使用するパスワードを指定します。省略時はinventory.yamlの値を使用します。"
device_type_help = "Netmikoにおけるデバイスタイプを指定します（例: cisco_ios）。省略時は 'cisco_ios' です。"
port_help = "SSH接続に使用するポート番号を指定します（デフォルト: 22）"
timeout_help = "SSH接続のタイムアウト秒数を指定します（デフォルト: 10秒）"
log_help = ("実行結果をログファイルとして保存します。\n"
           "保存先: logs/configure/\n"
           "保存名: yearmmdd-hhmmss_[hostname]_[config_or_config_list]\n"
           "example: 20250504-235734_R0_show-ip-int-brief.log")
memo_help = ("ログファイル名に付加する任意のメモ（文字列）を指定します。\n"
             "保存先: logs/configure/\n"
             "保存名: yearmmdd-hhmmss_[hostname]_[config_or_config_list]_[memo]\n"
             "example 20250506-125600_R0_show-ip-int-brief_memo.log")
workers_help = ("並列実行するワーカースレッド数を指定します。\n"
                "指定しない場合は sys_config.yaml の executor.default_workers を参照します。\n"
                "そこにも設定が無いときは、グループ台数と 規定上限(DEFAULT_MAX_WORKERS) の小さい方が自動で採用されます。")


######################
### PARSER_SECTION ###
######################
netmiko_configure_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
# "-h" はhelpと競合するから使えない。
netmiko_configure_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_configure_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_configure_parser.add_argument("-d", "--device_type", type=str, default="cisco_ios", help=device_type_help)
netmiko_configure_parser.add_argument("-P", "--port", type=int, default=22, help=port_help)
netmiko_configure_parser.add_argument("-t", "--timeout", type=int, default=10, help=timeout_help)
netmiko_configure_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_configure_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)
netmiko_configure_parser.add_argument("-w", "--workers", type=int, default=None, metavar="N", help=workers_help)

# mutually exclusive
target_node = netmiko_configure_parser.add_mutually_exclusive_group(required=True)
target_node.add_argument("-i", "--ip", type=str, nargs="?", default=None, help=ip_help)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help)

target_command = netmiko_configure_parser.add_mutually_exclusive_group(required=True)
target_command.add_argument("-L", "--config-list", type=str, default="", help=command_list_help)



def validate_config_list(args, device):
    """
    config-lists.yaml に基づいて、指定されたコンフィグリストの存在を検証する。

    Args:
        args: argparse.Namespace - コマンドライン引数
        device: dict - 接続対象のデバイス情報（device_type含む）

    Returns:
        config_lists_data

    Raises:
        FileNotFoundError: config-lists.yaml が存在しない場合
        ValueError: device_type または config_list が未定義の場合
    """

    # ✅ config-listが指定されている場合は先に存在チェック

    if not args.config_list:
        msg = "-L or --config_list が指定されていないケロ🐸"
        print_error(msg)
        raise ValueError(msg)

    if args.config_list:
        config_lists_path = Path("config-lists.yaml")
        if not config_lists_path.exists():
            msg = "config-lists.yaml が見つからないケロ🐸"
            print_error(msg)
            raise FileNotFoundError(msg)

        yaml = YAML()
        with config_lists_path.open("r") as f:
            config_lists_data = yaml.load(f)

        device_type = device["device_type"]

        if device_type not in config_lists_data["config_lists"]:
            msg = f"デバイスタイプ '{device_type}' はconfig-lists.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)

        if args.config_list not in config_lists_data["config_lists"][device_type]:
            msg = f"コマンドリスト '{args.config_list}' はconfig-lists.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)
    
    return config_lists_data


def apply_config_list(connection, hostname, args, device):

    if args.config_list:
        try:
            config_lists_data = validate_config_list(args, device)
            configure_commands = config_lists_data["config_lists"][device["device_type"]][f"{args.config_list}"]["config_list"]
        except Exception as e:
            msg = f"[{hostname}] config-lists.yamlの構造がおかしいケロ🐸 詳細: {e}"
            print_error(msg)
            raise KeyError(msg)

        result_output_string = connection.send_config_set(configure_commands, strip_prompt=False, strip_command=False)
        return result_output_string

    else:
        raise ValueError("config_listが必要ケロ🐸")


def _handle_configure(device: dict, args, poutput, hostname):
    """
    デバイス接続〜設定変更〜ログ保存までをまとめて処理するラッパー関数。

    Args:
        device (dict): 接続情報を含むデバイス辞書
        args: コマンドライン引数
        poutput: cmd2 の出力関数
        hostname (str): ログファイル名などに使うホスト識別子
    """
    
    # ✅ 1. 接続とプロンプト取得
    try:
        connection = _connect_to_device(device, hostname)
        print_success(f"NODE: {hostname} 🔗接続成功ケロ🐸")
        try:  
            ensure_enable_mode(connection)        
            prompt, hostname = _get_prompt(connection)
        except ValueError:
            connection.disconnect()
            return
    except ConnectionError as e:
        print_error(str(e))
        return
    
    
    # ✅ 2. 設定変更（config-list）
    try:
        result_output_string = apply_config_list(connection, hostname, args, device)
    except (KeyError, ValueError) as e:
        print_error(str(e))
        connection.disconnect()
        return

    # ✅ 3. 接続終了
    connection.disconnect()

    # ✅ 4. ログ保存（--log指定時のみ）
    if args.log:
        _save_log(result_output_string, hostname, args, mode="configure")

    # ✅ 5. 結果表示
    print_info(f"NODE: {hostname} 📄OUTPUTケロ🐸")
    poutput(result_output_string)
    print_success(f"NODE: {hostname} 🔚実行完了ケロ🐸")


@cmd2.with_argparser(netmiko_configure_parser)
def do_configure(self, args):

    if args.ip:
        device, hostname = _build_device_and_hostname(args)
        _handle_configure(device,  args, self.poutput, hostname)
        return
    
    elif args.host or args.group:
        try:
            inventory_data = _load_and_validate_inventory(host=args.host, group=args.group)
        
        except (FileNotFoundError, ValueError) as e:
            print_error(self.poutput, str(e))
            return

        
    
    if args.host:
        device, hostname = _build_device_and_hostname(args, inventory_data)
        _handle_configure(device, args, self.poutput, hostname)
        return

    elif args.group:
        device_list, hostname_list = _build_device_and_hostname(args, inventory_data)

        max_workers = _default_workers(len(device_list), args)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:

            futures = []
            for device, hostname in zip(device_list, hostname_list):
                future = pool.submit(_handle_configure, device, args, self.poutput, hostname)
                futures.append(future)

            for future in as_completed(futures):
                future.result()

