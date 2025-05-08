import argparse
from datetime import datetime
from pathlib import Path
from netmiko import ConnectHandler
import cmd2
from ruamel.yaml import YAML
from message import print_info, print_success, print_warning, print_error, ask


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

# mutually exclusive
target_node = netmiko_execute_parser.add_mutually_exclusive_group(required=True)
target_node.add_argument("-i", "--ip", type=str, nargs="?", default=None, help=ip_help)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help)

target_command = netmiko_execute_parser.add_mutually_exclusive_group(required=True)
target_command.add_argument("-c", "--command", type=str, default="", help=command_help)
target_command.add_argument("-L", "--commands-list", type=str, default="", help=command_list_help)


def _connect_to_device(device: dict, hostname_for_log:str):

    try:   
        connection = ConnectHandler(**device)
        # TODO: 将来的にはdevice_typeでCisco以外の他機種にも対応。
        node_prompt = connection.find_prompt()
        hostname = node_prompt.strip("#>")
        return connection, node_prompt, hostname

    except Exception as e:
        raise ConnectionError(f"[{hostname_for_log}]に接続できないケロ。🐸 \n {e}")


def _execute_commands_on_device(connection, node_prompt, hostname_for_log, args, poutput, device) -> str:
    
    if args.command:
        output = connection.send_command(args.command)
        full_output = f"{node_prompt} {args.command}\n{output}"

        return full_output

    elif args.commands_list:
        commands_lists_path = Path("commands-lists.yaml")
        if not commands_lists_path.exists():
            raise FileNotFoundError("commands-lists.yamlが見つからないケロ🐸")

        yaml = YAML()
        with open(commands_lists_path, "r") as file_commands_lists:
            commands_lists_data = yaml.load(file_commands_lists)

            device_type = device["device_type"]

            if device_type not in commands_lists_data["commands_lists"]:
                print_error(poutput, f"デバイスタイプ '{device_type}' はcommands-lists.yamlに存在しないケロ🐸")
                return "" # エラー時には空文字列を返す。
            if args.commands_list not in commands_lists_data["commands_lists"][f"{args.device_type}"]:
                print_error(poutput, f"コマンドリスト '{args.commands_list}' はcommands-lists.yamlに存在しないケロ🐸")
                return "" # エラー時には空文字列を返す。

            try:
                exec_commands = commands_lists_data["commands_lists"][f"{device_type}"][f"{args.commands_list}"]["commands_list"]
            except Exception as e:
                raise KeyError(f"[{hostname_for_log}] commands-lists.yamlの構造がおかしいケロ🐸")

            full_output_list = []

            for command in exec_commands:
                output = connection.send_command(command)
                full_output = f"{node_prompt} {command}\n{output}"
                full_output_list.append(full_output)
            
            return "\n".join(full_output_list)


def _execute_on_device(device: dict, args, poutput, hostname_for_log) -> None:

 # ✅ commands-listが指定されている場合は先に存在チェック
    if args.commands_list:
        commands_lists_path = Path("commands-lists.yaml")
        if not commands_lists_path.exists():
            print_error(poutput, "commands-lists.yaml が見つからないケロ🐸")
            return

        yaml = YAML()
        with commands_lists_path.open("r") as f:
            data = yaml.load(f)

        device_type = device["device_type"]
        if device_type not in data["commands_lists"]:
            print_error(poutput, f"デバイスタイプ '{device_type}' はcommands-lists.yamlに存在しないケロ🐸")
            return

        if args.commands_list not in data["commands_lists"][device_type]:
            print_error(poutput, f"コマンドリスト '{args.commands_list}' はcommands-lists.yamlに存在しないケロ🐸")
            return

    try:
        connection, node_prompt, real_hostname = _connect_to_device(device, hostname_for_log)
    except ConnectionError as e:
        print_error(poutput, str(e))
        return

    try:
        full_output_or_full_output_list = _execute_commands_on_device(connection, node_prompt, hostname_for_log, args, poutput, device)
    except KeyError as e:
        print_error(poutput, str(e))
        return

    connection.disconnect()

    if args.memo and not args.log:
        print_warning(poutput, "--memo は --log が指定されているときだけ有効ケロ🐸")
    
    if args.log == True:
        date_str = datetime.now().strftime("%Y%m%d")
        log_dir = Path("logs") / "execute" / date_str
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if args.command:
            sanitized_command = args.command.replace(" ", "-")
        elif args.commands_list:
            sanitized_command = args.commands_list.replace(" ", "-")
        else:
            raise ValueError("args.command または args.commands_list のどちらかが必須ケロ！🐸")

        if args.memo == "":
            file_name = f"{timestamp}_{real_hostname}_{sanitized_command}.log"
        else:
            file_name = f"{timestamp}_{real_hostname}_{sanitized_command}_{args.memo}.log"
        
        log_path = log_dir / file_name

        with open(log_path, "w") as log_file:
            log_file.write(full_output_or_full_output_list)
            print_info(poutput, "💾ログ保存モードONケロ🐸🔛")
            print_success(poutput, "🔗接続成功ケロ🐸")
            poutput(full_output_or_full_output_list)
            print_success(poutput, f"💾ログ保存完了ケロ🐸⏩⏩⏩ {log_path}")

    else:
        print_success(poutput, "🔗接続成功ケロ🐸")
        poutput(full_output_or_full_output_list)


def _load_and_validate_inventory(args, poutput):

    inventory_path = Path("inventory.yaml")
    if not inventory_path.exists():
        raise FileNotFoundError("inventory.yamlが存在しないケロ🐸")

    yaml = YAML()
    with open(inventory_path, "r") as inventory:
        inventory_data = yaml.load(inventory)

    if args.host:
        if args.host not in inventory_data["all"]["hosts"]:
            print_error(poutput, f"ホスト '{args.host}' はinventory.yamlに存在しないケロ🐸")
            return None
    elif args.group:
        if args.group not in inventory_data["all"]["groups"]:
            print_error(poutput, f"グループ '{args.group}' はinventory.yamlに存在しないケロ🐸")
            return None
    
    return inventory_data
    

def _build_device_and_hostname(args, inventory_data=None):

    if args.ip:
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
    
    elif args.host:
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

    elif args.group:
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


@cmd2.with_argparser(netmiko_execute_parser)
def do_execute(self, args):

    if args.ip:
        device, hostname_for_log = _build_device_and_hostname(args)
        _execute_on_device(device, args, self.poutput, hostname_for_log)
    

    elif args.host:
        inventory_data = _load_and_validate_inventory(args, self.poutput)
        if inventory_data is None:
            return
              
        device, hostname_for_log = _build_device_and_hostname(args, inventory_data)
        _execute_on_device(device, args, self.poutput, hostname_for_log)


    elif args.group:
        # TODO: 将来的には並列処理を実装。
        inventory_data = _load_and_validate_inventory(args, self.poutput)            
        if inventory_data is None:
            return

        device_list, hostname_for_log_list = _build_device_and_hostname(args, inventory_data)
        for device, hostname_for_log in zip(device_list, hostname_for_log_list):
            _execute_on_device(device, args, self.poutput, hostname_for_log)