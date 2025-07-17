import argparse
import cmd2
import time
from datetime import datetime
from pathlib import Path
import re

from netmiko.utilities import check_serial_port
from netmiko import ConnectHandler

from message import print_error, print_info, print_warning, print_success
from executor import _load_and_validate_inventory, validate_commands_list, _save_log
from utils import wait_for_prompt_returned

from rich.console import Console


#######################
###  CONST_SECTION  ### 
#######################
DELAY_FACTOR = 3
SLEEP_TIME = 1


######################
###  HELP_SECTION  ### 
######################
serial_help = ("使用するシリアルポートを指定します。\n"
               "example: console --serial /dev/ttyUSB0\n")
baudrate_help = ("使用するbaudrateを指定します。\n"
                 "example: console --baudrate 9600")
username_help = "console接続に使用するユーザー名を指定します。"
password_help = "console接続に使用するパスワードを指定します。"
device_type_help = "Netmikoにおけるデバイスタイプを指定します（例: cisco_ios）。省略時は 'cisco_ios_serial' です。"
host_help = ("inventory.yamlに定義されたホスト名を指定します。\n"
             "--host 指定時は他オプション（username, password, device_type, baudrate）は無視されます。")
read_timeout_help = ("send_command の応答待ち時間（秒）。\n"
                     "重いコマンド（例: show tech）用に指定します。\n"
                     "console --host R1 -c 'show tech' --read_timeout 1000"
                     "default: 30")
log_help = ("実行結果をログファイルとして保存します。\n"
           "保存先: logs/console/\n"
           "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]\n"
           "example: 20250504-235734_R0_show-ip-int-brief.log")
memo_help = ("ログファイル名に付加する任意のメモ（文字列）を指定します。\n"
             "保存先: logs/console/\n"
             "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]_[memo]\n")
command_help = "1つのコマンドを直接指定して実行します。"
command_list_help = "コマンドリスト名（commands-lists.yamlに定義）を指定して実行します。" \
                    "device_typeはホストから自動で選択されます。"

######################
### PARSER_SECTION ###
######################
netmiko_console_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
# "-h" はhelpと競合するから使えない。
netmiko_console_parser.add_argument("-s", "--serial", type=str, default="/dev/ttyUSB0", help=serial_help)
netmiko_console_parser.add_argument("-b", "--baudrate", type=int, default=9600, help=baudrate_help)
netmiko_console_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_console_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_console_parser.add_argument("-d", "--device_type", type=str, default="", help=device_type_help)
netmiko_console_parser.add_argument("-r", "--read_timeout", type=int, default=30, help=read_timeout_help)
netmiko_console_parser.add_argument("-H", "--host", type=str, default="", help=host_help)
netmiko_console_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_console_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)

# mutually exclusive
target_command = netmiko_console_parser.add_mutually_exclusive_group(required=True)
target_command.add_argument("-c", "--command", type=str, default="", help=command_help)
target_command.add_argument("-L", "--commands-list", type=str, default="", help=command_list_help)



console = Console()

@cmd2.with_argparser(netmiko_console_parser)
def do_console(self, args):
    """
    Netmiko を用いてシリアルコンソール接続を行い、コマンドを実行します。

    概要:
        - 指定されたシリアルポート（--serial）とボーレート（--baudrate）で接続
        - inventory.yaml からのホスト情報読み取りにも対応（--host）
        - enable モードへの昇格を自動で試行（失敗時は警告）
        - 単一コマンド（--command）またはコマンドリスト（--commands-list）の実行
        - 実行結果をログファイルに保存するオプション（--log）

    注意:
        - 応答の遅いコマンドに備え、--read_timeout オプションで待機時間を調整可能
        - 実行後は自動で disable して enable モードを離脱（失敗しても続行）
        - prompt 検出のために wait を挟むことで、確実な同期を行っています

    Args:
        args (argparse.Namespace): コマンドライン引数

    Raise:
        ValueError: inventory 取得失敗、enable モード移行失敗、YAML 読み取り失敗など
    """

    try:
        serial_port = check_serial_port(args.serial)
        print_info(f"✅ 使用可能なポート: {serial_port}")
    except ValueError as e:
        print_error(str(e))
        return

    if args.host:
        # ✅ inventory.yaml の存在チェックと --host の妥当性確認
        # ※ 接続前なので try/except で安全に中断する
        try:
            inventory_data = _load_and_validate_inventory(host=args.host)
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            return
        node_info = inventory_data.get("all", {}).get("hosts", {}).get(f"{args.host}", {})
        if not node_info:
            msg = f"inventoryにホスト '{args.host}' が見つからないケロ🐸"
            print_error(msg)
            raise KeyError(msg)

        # deviceについては stopbits / parity / bytesize / xonxoff / rtscts / timeout などの拡張が想定される。
        device = {
            "device_type": args.device_type or node_info.get("device_type", "cisco_ios_serial"),
            "serial_settings": {
                "port": serial_port,
                "baudrate": int(node_info.get("baudrate", "9600"))
            },
            "username": args.username or node_info.get("username", ""),     # ログイン要求があれば
            "password": args.password or node_info.get("password", "")     # 同上
        }

    else:
        device = {
            "device_type": args.device_type or "cisco_ios_serial",
            "serial_settings": {
                "port": serial_port,
                "baudrate": args.baudrate
            },
            "username": args.username,     # ログイン要求があれば
            "password": args.password      # 同上
        }

    connection = ConnectHandler(**device)

    connection.set_base_prompt()
    wait_for_prompt_returned(connection, sleep_time=SLEEP_TIME)
    prompt = connection.find_prompt()
    hostname = connection.base_prompt

    expect_prompt = rf"{re.escape(hostname)}[#>]"
    
    if not connection.check_enable_mode():
        try: 
            connection.enable()
        except Exception as e:
            msg = f"Enableモードに移行できなかったケロ🐸 {e}"
            print_error(msg)
            raise ValueError(msg)

    if args.command:
        output = connection.send_command(args.command, delay_factor=DELAY_FACTOR, expect_string=expect_prompt, read_timeout=args.read_timeout)
        full_output = f"{prompt} {args.command}\n{output}\n"
        result_output_string = full_output
    # execute_commands_listと違う部分はhostname_for_log -> hostname send_commandでdelay_factorを渡している。あとは一緒。
    elif args.commands_list:
        try:
            commands_lists_data = validate_commands_list(args, device)
            exec_commands = commands_lists_data["commands_lists"][device["device_type"]][f"{args.commands_list}"]["commands_list"]
        except Exception as e:
            msg = f"[{hostname}] commands-lists.yamlの構造がおかしいケロ🐸 詳細: {e}"
            print_error(msg)
            raise KeyError(msg)

        full_output_list = []

        for command in exec_commands:
            output = connection.send_command(command, delay_factor=DELAY_FACTOR, expect_string=expect_prompt, read_timeout=args.read_timeout)
            full_output = f"{prompt} {command}\n{output}\n"
            full_output_list.append(full_output)
        
        result_output_string =  "\n".join(full_output_list)

    # ログの保存
    if args.log:
        _save_log(result_output_string, hostname, args, mode="console")

    self.poutput(result_output_string)
    wait_for_prompt_returned(connection, sleep_time=SLEEP_TIME)

    if connection.check_enable_mode():
        try:
            # exit enable 前に余裕を持たせないと、応答遅延で失敗することがあるケロ🐸
            print_info("🔽 enableモードから抜けるために disable 実行するケロ🐸")
            connection.send_command("disable", delay_factor=DELAY_FACTOR, expect_string=expect_prompt)

            if connection.check_enable_mode():
                msg = "Enableモードから移行できなかったケロ🐸（disable効かなかった）"
                print_warning(msg)

        except Exception as e:
            msg = f"Enableモードから移行できなかったケロ🐸 {e}"
            print_warning(msg)
    
    try:
        connection.disconnect()
    except Exception as e:
        msg = f"disconnectに失敗したケロ🐸 詳細: {e}"
        print_warning(msg)
    



